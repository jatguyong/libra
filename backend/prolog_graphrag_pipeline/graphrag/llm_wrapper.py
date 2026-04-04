"""LLM wrapper and embeddings for the GraphRAG pipeline.

Provides GraphRAGLLM (extends neo4j_graphrag's OllamaLLM for interface compatibility)
and TogetherAIEmbeddings for the Together AI embeddings API.
"""

import time
import threading
import logging
from typing import Union

from neo4j_graphrag.llm import LLMInterface
from neo4j_graphrag.llm.types import LLMResponse
from neo4j_graphrag.embeddings.base import Embedder

from ..llm_config import (
    ENCODER_MODEL_NAME as _LLM_MODEL,
    get_openai_client,
    log_llm_event, retry_with_exponential_backoff,
)

logger = logging.getLogger(__name__)

ENCODER_MODEL = _LLM_MODEL
RETRIEVER_MODEL = _LLM_MODEL


# -- Embeddings ---------------------------------------------------------------

class TogetherAIEmbeddings(Embedder):
    """Embedder that calls the Together AI OpenAI-compatible embeddings endpoint."""

    def embed_query(self, text: str):
        from ..llm_config import EMBED_MODEL
        _client = get_openai_client()
        start_time = time.perf_counter()

        invoke_func = retry_with_exponential_backoff(_client.embeddings.create)
        response = invoke_func(model=EMBED_MODEL, input=text)

        duration = time.perf_counter() - start_time
        log_llm_event("EMBED_QUERY", duration=duration)
        return response.data[0].embedding

    async def async_embed_chunks(self, texts: list[str]) -> list[list[float]]:
        """Batch embed a list of texts using the Together AI API."""
        from ..llm_config import EMBED_MODEL
        import asyncio
        _client = get_openai_client()
        loop = asyncio.get_event_loop()

        def _do_batch():
            start_time = time.perf_counter()
            invoke_func = retry_with_exponential_backoff(_client.embeddings.create)
            resp = invoke_func(model=EMBED_MODEL, input=texts)
            duration = time.perf_counter() - start_time
            log_llm_event(f"EMBED_BATCH_{len(texts)}", duration=duration)
            return [d.embedding for d in resp.data]

        return await loop.run_in_executor(None, _do_batch)


# Monkeypatch neo4j_graphrag's TextChunkEmbedder to use batching when available
try:
    from neo4j_graphrag.experimental.components.embedder import TextChunkEmbedder
    from neo4j_graphrag.experimental.components.types import TextChunks, TextChunk
    _original_embedder_run = TextChunkEmbedder.run

    async def _patched_embedder_run(self, text_chunks: Union[TextChunks, dict]) -> TextChunks:
        if hasattr(self._embedder, "async_embed_chunks"):
            if isinstance(text_chunks, dict):
                raw_chunks = text_chunks.get("chunks", [])
                chunk_objs = [
                    TextChunk(**c) if isinstance(c, dict) else c
                    for c in raw_chunks
                ]
            else:
                chunk_objs = text_chunks.chunks

            texts = [c.text for c in chunk_objs]
            embeddings = []
            batch_size = 100
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                batch_emb = await self._embedder.async_embed_chunks(batch)
                embeddings.extend(batch_emb)

            chunks = []
            for i, c in enumerate(chunk_objs):
                metadata = c.metadata if c.metadata else {}
                metadata["embedding"] = embeddings[i]
                chunks.append(TextChunk(text=c.text, index=c.index, metadata=metadata, uid=c.uid))
            return TextChunks(chunks=chunks)
        else:
            return await _original_embedder_run(self, text_chunks)

    TextChunkEmbedder.run = _patched_embedder_run
except ImportError:
    pass


# -- LLM Wrapper --------------------------------------------------------------

class GraphRAGLLM(LLMInterface):
    """LLM wrapper that routes all calls through the Together AI API.

    Inherits ``LLMInterface`` (the neo4j_graphrag abstract base) so the
    library treats it as a valid LLM without requiring Ollama.
    Every actual invocation goes through the OpenAI-compatible Together AI
    client configured in ``llm_config``.
    """

    def __init__(self, model_name: str = "", model_params: dict | None = None, **kwargs):
        # LLMInterface expects (model_name, model_params); do NOT call OllamaLLM.__init__
        self.model_name = model_name
        self.model_params = model_params or {}

    def _clean_response_text(self, text: str) -> str:
        """Extract JSON object from response text.

        SimpleKGPipeline requires {"nodes": [...], "relationships": [...]}.
        """
        if not text:
            return ""
        obj_start = text.find('{')
        obj_end = text.rfind('}')
        if obj_start != -1 and obj_end != -1 and obj_start < obj_end:
            return text[obj_start:obj_end + 1]
        return text

    def _clean_prompt(self, text: str) -> str:
        """Remove newlines from PDF-extracted prose but preserve structured prompts.

        Structured prompts (KBPedia batch filter, concept filter) use intentional
        newlines for formatting — collapsing them confuses the model.
        """
        STRUCTURED_MARKERS = ("Concept: '", "  - ", "Facts:\n", "Candidates (")
        if any(m in text for m in STRUCTURED_MARKERS):
            return text
        return text.replace('\n', ' ')

    def _clean_input_data(self, input_data):
        """Apply _clean_prompt to a string or list of message dicts."""
        if isinstance(input_data, str):
            return self._clean_prompt(input_data)
        elif isinstance(input_data, list):
            cleaned_list = []
            for msg in input_data:
                cleaned_msg = msg.copy() if isinstance(msg, dict) else msg
                if isinstance(cleaned_msg, dict) and 'content' in cleaned_msg:
                    cleaned_msg['content'] = self._clean_prompt(str(cleaned_msg['content']))
                cleaned_list.append(cleaned_msg)
            return cleaned_list
        return input_data

    def _openai_invoke(self, input, message_history=None, system_instruction=None):
        """Route through the Together AI OpenAI-compatible client with retries and hard timeouts."""
        _client = get_openai_client()

        if isinstance(input, list):
            messages = input
        else:
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": str(system_instruction)})
            if message_history:
                messages.extend([{"role": m.get("role", "user"), "content": m.get("content", "")} for m in message_history])
            messages.append({"role": "user", "content": str(input)})

        log_input = str(messages[-1]['content']) if messages else ""
        if len(log_input) > 100:
            logger.debug("SENT PROMPT: %s", log_input)

        max_retries = 5
        timeout_sec = 120.0

        result_holder = [None]
        error_holder = [None]

        def _do_invoke():
            response = _client.chat.completions.create(
                model=ENCODER_MODEL,
                messages=messages,
                temperature=0.3,
                timeout=timeout_sec,
                max_tokens=4096,
                logprobs=True
            )
            response.content = {
                "answer": response.choices[0].message.content,
                "logprobs": response.choices[0].logprobs.token_logprobs
            }
            return response

        def _target():
            try:
                start_time = time.perf_counter()
                backoff_invoke = retry_with_exponential_backoff(_do_invoke, max_retries=max_retries)
                resp = backoff_invoke()
                duration = time.perf_counter() - start_time
                log_llm_event("GRAG_INVOKE", duration=duration)
                result_holder[0] = resp
            except Exception as e:
                log_llm_event("GRAG_INVOKE_FAIL", error=str(e))
                error_holder[0] = e

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout=(timeout_sec * (max_retries + 1)) + 30)

        if thread.is_alive():
            logger.error("LLM call timed out even after retries.")
            return LLMResponse(content="Error: LLM call timed out.")

        if error_holder[0]:
            logger.error("LLM call failed: %s", error_holder[0])
            return LLMResponse(content=f"Error: LLM call failed: {error_holder[0]}")

        response = result_holder[0]
        if response:
            content = response.choices[0].message.content or ""
            logger.debug("RAW RESPONSE: %s", content[:500])
            return LLMResponse(content=self._clean_response_text(content))

    def invoke(self, input, message_history=None, system_instruction=None, **kwargs):
        return self._openai_invoke(input, message_history, system_instruction)

    async def ainvoke(self, input, message_history=None, system_instruction=None, **kwargs):
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._openai_invoke, input, message_history, system_instruction)


# -- Model initialization -----------------------------------------------------

def initialize_models():
    """Create the encoder LLM, retriever LLM, and embedder instances."""
    from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
    from openai import RateLimitError, APITimeoutError, APIConnectionError

    encoder_llm = GraphRAGLLM(
        model_name=ENCODER_MODEL,
        model_params={
            "keep_alive": "20m",
            "options": {
                "temperature": 0,
                "num_ctx": 4096,
                "format": "json",
                "repeat_penalty": 1.2,
                "seed": 42
            }
        }
    )

    # Wrap encoder with tenacity retry for robustness against transient API errors
    original_invoke = encoder_llm.invoke

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=60),
        stop=stop_after_attempt(8),
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        reraise=True
    )
    def robust_invoke(*args, **kwargs):
        logger.debug("Sending chunk to LLM...")
        return original_invoke(*args, **kwargs)

    encoder_llm.invoke = robust_invoke

    retriever_llm = GraphRAGLLM(
        model_name=RETRIEVER_MODEL,
        model_params={
            "keep_alive": "20m",
            "options": {
                "temperature": 0.1,
                "num_ctx": 4096,
                "format": "json",
                "repeat_penalty": 1.2,
                "seed": 42
            }
        }
    )

    embedder = TogetherAIEmbeddings()

    return encoder_llm, retriever_llm, embedder
