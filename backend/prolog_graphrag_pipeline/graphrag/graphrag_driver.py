import neo4j
from neo4j_graphrag.llm import OllamaLLM
from neo4j_graphrag.embeddings.ollama import OllamaEmbeddings
from neo4j_graphrag.experimental.components.text_splitters.fixed_size_splitter import FixedSizeSplitter
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.generation import GraphRAG
from .encoder import process_pdf_documents, process_text_context, process_context, extract_query_and_context
from .retriever import generate, create_retriever
from .config import GRAPHRAG_TEMPLATE, GRAPHRAG_FALLBACK_TEMPLATE
import os
import glob
from .config import PROMPT_TEMPLATE, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD, SCHEMA_CONFIG, STATIC_SCHEMA # added dot for relative import, assuming config.py is in the same directory as graphrag_driver.py
# However, this will fail when you run this file directly. For debugging purposes, you can run 'python -m graphrag-pipeline.graphrag.graphrag_driver' in the terminal.
import asyncio
import time
import threading
import sys
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from openai import RateLimitError, APITimeoutError, APIConnectionError
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline

# Persistent event loop to avoid "RuntimeError: Event loop is closed" on Windows.
# asyncio.run() creates and destroys a new loop each call, but httpx/httpcore
# transport cleanup callbacks fire AFTER the loop is closed, causing a crash.
# By reusing a single loop, we keep it alive for the entire process lifetime.
_persistent_loop = None

def _run_async(coro):
    """Run an async coroutine using a persistent event loop (avoids httpx cleanup crash)."""
    global _persistent_loop
    if _persistent_loop is None or _persistent_loop.is_closed():
        _persistent_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_persistent_loop)
    return _persistent_loop.run_until_complete(coro)

from pathlib import Path

from ..llm_config import ENCODER_MODEL_NAME as _LLM_MODEL, USE_TOGETHER_API, get_openai_client, BASE_URL, API_KEY, log_llm_event, retry_with_exponential_backoff

if USE_TOGETHER_API:
    from neo4j_graphrag.embeddings.base import Embedder

    class TogetherAIEmbeddings(Embedder):
        """Embedder that calls the Together AI OpenAI-compatible embeddings endpoint."""
        def embed_query(self, text: str):
            from ..llm_config import EMBED_MODEL
            _client = get_openai_client()
            start_time = time.perf_counter()
            
            # Wrap with exponential backoff
            invoke_func = retry_with_exponential_backoff(_client.embeddings.create)
            
            response = invoke_func(
                model=EMBED_MODEL,
                input=text,
            )
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
                # The openai client can take a list of strings
                start_time = time.perf_counter()
                
                # Wrap with exponential backoff
                invoke_func = retry_with_exponential_backoff(_client.embeddings.create)
                
                resp = invoke_func(model=EMBED_MODEL, input=texts)
                duration = time.perf_counter() - start_time
                log_llm_event(f"EMBED_BATCH_{len(texts)}", duration=duration)
                return [d.embedding for d in resp.data]
            
            return await loop.run_in_executor(None, _do_batch)

    # Monkeypatch neo4j_graphrag's TextChunkEmbedder to use batching if available
    try:
        from neo4j_graphrag.experimental.components.embedder import TextChunkEmbedder
        from neo4j_graphrag.experimental.components.types import TextChunks, TextChunk
        _original_embedder_run = TextChunkEmbedder.run

        from typing import Union
        async def _patched_embedder_run(self, text_chunks: Union[TextChunks, dict]) -> TextChunks:
            if hasattr(self._embedder, "async_embed_chunks"):
                # Handle dictionary input
                if isinstance(text_chunks, dict):
                    raw_chunks = text_chunks.get("chunks", [])
                    # convert dict to TextChunk objects if needed
                    chunk_objs = []
                    for c in raw_chunks:
                        if isinstance(c, dict):
                            chunk_objs.append(TextChunk(**c))
                        else:
                            chunk_objs.append(c)
                else:
                    chunk_objs = text_chunks.chunks

                texts = [c.text for c in chunk_objs]
                embeddings = []
                batch_size = 100
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i+batch_size]
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

ENCODER_MODEL = _LLM_MODEL
RETRIEVER_MODEL = _LLM_MODEL

class DebugOllamaLLM(OllamaLLM):
    """Wrapper to clean input prompts and log raw LLM responses to debug.txt."""
    
    def _log_to_file(self, message: str):
        """Appends a message to debug.txt with UTF-8 encoding."""
        try:
            with open("debug.txt", "a", encoding="utf-8") as f:
                f.write(message + "\n")
        except Exception as e:
            print(f"[DebugOllamaLLM Error] Could not write to debug.txt: {e}")

    def _clean_response_text(self, text: str) -> str:
        """Helper: Extracts JSON object from the response string.

        Always prefers {…} objects because SimpleKGPipeline strictly requires
        {"nodes": […], "relationships": […]}. The triple filter (filter_triples_for_query)
        does its own independent [bracket] extraction and does NOT rely on this method
        to return arrays, so reverting to object-only is safe for both callers.
        """
        if not text:
            return ""
        obj_start = text.find('{')
        obj_end   = text.rfind('}')
        if obj_start != -1 and obj_end != -1 and obj_start < obj_end:
            return text[obj_start : obj_end + 1]
        return text   # nothing to strip — return as-is

    def _clean_prompt(self, text: str) -> str:
        """Removes newlines only from PDF-extracted prose.

        Structured filter prompts (KBPedia batch filter, concept filter) use
        intentional newlines to separate concept blocks. Stripping them collapses
        all structure into one line, which confuses the model and causes hangs.
        We detect structured prompts by the presence of known marker strings.
        """
        STRUCTURED_MARKERS = ("Concept: '", "  - ", "Facts:\n", "Candidates (")
        if any(m in text for m in STRUCTURED_MARKERS):
            return text   # preserve structured prompt formatting
        return text.replace('\n', ' ')

    def _clean_input_data(self, input_data):
        """Applies _clean_prompt either to a string or to the 'content' of a list of message dicts."""
        if isinstance(input_data, str):
            return self._clean_prompt(input_data)
        elif isinstance(input_data, list):
            # Neo4j GraphRAG passes List[LLMMessage] which are dicts with 'role' and 'content'
            cleaned_list = []
            for msg in input_data:
                cleaned_msg = msg.copy() if isinstance(msg, dict) else msg
                if isinstance(cleaned_msg, dict) and 'content' in cleaned_msg:
                    cleaned_msg['content'] = self._clean_prompt(str(cleaned_msg['content']))
                cleaned_list.append(cleaned_msg)
            return cleaned_list
        return input_data

    def _openai_invoke(self, input, message_history=None, system_instruction=None):
        """Route through the openai client when USE_TOGETHER_API=True with retries and hard timeouts."""
        from neo4j_graphrag.llm.types import LLMResponse
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

        # Log prompt if it's an answer generation (not just a tiny fragment)
        log_input = str(messages[-1]['content']) if messages else ""
        if len(log_input) > 100:
             self._log_to_file(f"\n--- [DEBUG] SENT PROMPT (Together AI) ---\n{log_input}\n----------------------------------")

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
                max_tokens=2048,
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
                # Use centralized exponential backoff
                backoff_invoke = retry_with_exponential_backoff(_do_invoke, max_retries=max_retries)
                resp = backoff_invoke()
                
                duration = time.perf_counter() - start_time
                log_llm_event(f"GRAG_INVOKE", duration=duration)
                result_holder[0] = resp
            except Exception as e:
                log_llm_event(f"GRAG_INVOKE_FAIL", error=str(e))
                error_holder[0] = e

        thread = threading.Thread(target=_target, daemon=True)
        thread.start()
        thread.join(timeout=(timeout_sec * (max_retries + 1)) + 30) # Wait for all retries

        if thread.is_alive():
            print(f"  > [LLM TIMEOUT] Together AI call timed out even after retries.", flush=True)
            return LLMResponse(content="Error: Together AI call timed out.")
        
        if error_holder[0]:
            print(f"  > [LLM ERROR] Together AI failed: {error_holder[0]}", flush=True)
            return LLMResponse(content=f"Error: Together AI failed: {error_holder[0]}")

        response = result_holder[0]
        if response:
            content = response.choices[0].message.content or ""
            self._log_to_file(f"\n=== [DEBUG] RAW RESPONSE (Together AI) ===\n{content}\n===================================")
            return LLMResponse(content=self._clean_response_text(content))

    def invoke(self, input, message_history=None, system_instruction=None, **kwargs):
        if USE_TOGETHER_API:
            return self._openai_invoke(input, message_history, system_instruction)
        kwargs.pop('response_format', None) # neo4j_graphrag OllamaLLM hates response_format
        clean_input = self._clean_input_data(input)
        
        # Format for logging
        log_input = clean_input if isinstance(clean_input, str) else str(clean_input)
        self._log_to_file(f"\n--- [DEBUG] SENT PROMPT (Sync) ---\n{log_input}\n----------------------------------")
        
        input_len = len(input) if isinstance(input, str) else len(str(input))
        print(f"  > Sending chunk to LLM ({input_len} chars)...", end="", flush=True)
        
        response = super().invoke(
            input=clean_input,
            message_history=message_history,
            system_instruction=system_instruction
        )
        print(" Done!")
        
        raw_content = response.content if hasattr(response, 'content') else str(response)
        self._log_to_file(f"\n=== [DEBUG] RAW RESPONSE (Sync) ===\n{raw_content}\n===================================")
        
        clean_content = self._clean_response_text(raw_content)
        if hasattr(response, 'content'):
            response.content = clean_content
            return response
        else:
            from neo4j_graphrag.llm.types import LLMResponse
            return LLMResponse(content=clean_content)

    async def ainvoke(self, input, message_history=None, system_instruction=None, **kwargs):
        if USE_TOGETHER_API:
            import asyncio
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self._openai_invoke, input, message_history, system_instruction)
        kwargs.pop('response_format', None)
        clean_input = self._clean_input_data(input)
        
        log_input = clean_input if isinstance(clean_input, str) else str(clean_input)
        self._log_to_file(f"\n--- [DEBUG] SENT PROMPT (Async) ---\n{log_input}\n----------------------------------")
        
        input_len = len(input) if isinstance(input, str) else len(str(input))
        print(f"  > [Async] Sending chunk to LLM ({input_len} chars) and waiting for extraction...", end="", flush=True)
        
        # Bypass neo4j-graphrag's ainvoke and its broken rate limit decorator
        # Call the native async_client from ollama directly
        from neo4j_graphrag.llm.types import LLMResponse
        try:
            if isinstance(clean_input, str):
                messages = self.get_messages(clean_input, message_history=message_history, system_instruction=system_instruction)
            else:
                messages = self.get_messages_v2(clean_input)
                
            response_obj = await self.async_client.chat(
                model=self.model_name,
                messages=messages,
                options={**self.model_params, **kwargs},
            )
            raw_content = response_obj.message.content or ""
            response = LLMResponse(content=raw_content)
        except Exception as e:
            print(f"\n[DebugOllamaLLM Error] Async call failed: {e}")
            raise
        
        print(" Done!")
        
        self._log_to_file(f"\n=== [DEBUG] RAW RESPONSE (Async) ===\n{raw_content}\n===================================")
        
        clean_content = self._clean_response_text(raw_content)
        if hasattr(response, 'content'):
            response.content = clean_content
            return response
        else:
            return clean_content


neo4j_driver = None


def initialize_models():
    encoder_llm = DebugOllamaLLM(
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

    original_invoke = encoder_llm.invoke

    # 2. Define the retry rules using Tenacity decorators
    @retry(
        # Wait exponentially: 2s, 4s, 8s, 16s... up to a max of 60 seconds per wait
        wait=wait_exponential(multiplier=1, min=2, max=60),
        
        # Give up completely after 8 failed attempts to prevent infinite hangs
        stop=stop_after_attempt(8),
        
        # ONLY retry on network or rate limit errors (don't retry on bad prompts)
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIConnectionError)),
        
        reraise=True # If it fails 8 times, raise the error so you know it died
    )
    def robust_invoke(*args, **kwargs):
        print("DEBUG PROLOG-GRAPHRAG:Sending chunk to LLM...")
        return original_invoke(*args, **kwargs)

    # 3. Apply the monkey-patch to your LLM instance
    encoder_llm.invoke = robust_invoke
    
    retriever_llm = DebugOllamaLLM(
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

    if USE_TOGETHER_API:
        from ..llm_config import EMBED_MODEL
        embedder = TogetherAIEmbeddings()
        # print(f"Together AI embedder loaded ({EMBED_MODEL}).")
    else:
        from ..llm_config import EMBED_MODEL
        embedder = OllamaEmbeddings(model=EMBED_MODEL)
        print("Ollama embedder loaded.")

    return encoder_llm, retriever_llm, embedder


def setup_kg_pipeline(llm, embedder) -> SimpleKGPipeline    :
    STATIC_SCHEMA = { # NOTE: Due to how 'EXTRACTED' works, the prompt used by SimpleKGPipeline is bad and does not constrain the output to only JSON format. We can create a custom KG Pipeline but for now we use this to skip it entirely.
        "node_types": [
            "Concept",      # The heavy lifter: covers Theorems, Ideas, Theories, Terms
            "Person",       # Key figures: Socrates, Einstein, Historical Leaders
            "Event",        # Occurrences: Wars, Experiments, Historical Periods
            "Definition",   # Crucial for education: Explicit statements of meaning
            "Example",      # Grounding: Specific instances (e.g., "Pingu" or "3")
            "Topic"         # The Field: "Mathematics", "Philosophy", "Biology"
        ],
        "relationship_types": [
            "RELATED_TO",   # Generic connection
            "IS_A",         # Hierarchy: "Calculus IS_A Topic", "Penguin IS_A Bird"
            "PART_OF",      # Composition: "Cell PART_OF Tissue"
            "CAUSES",       # Logic/History: "War CAUSES Famine", "Premise CAUSES Conclusion"
            "DEFINES",      # Concept -> Definition
            "ILLUSTRATES"   # Example -> Concept ("Pingu ILLUSTRATES Non-flying bird")
        ]
    }
    chunk_splitter = FixedSizeSplitter(chunk_size=450, chunk_overlap=50) # OPT2: reduced from 1200/150 → fewer tokens per extraction call
    
    schema = STATIC_SCHEMA if SCHEMA_CONFIG.name == "STATIC" else "EXTRACTED"

    kg_builder_pdf = SimpleKGPipeline(
        llm=llm,
        driver=neo4j_driver,
        embedder=embedder,
        entities=schema["node_types"],         
        relations=schema["relationship_types"],  
        prompt_template=PROMPT_TEMPLATE,
        from_pdf=True,
        text_splitter=chunk_splitter,
        perform_entity_resolution=True,
        on_error="IGNORE",
        
    )
    
    kg_builder_text = SimpleKGPipeline(
        llm=llm,
        driver=neo4j_driver,
        embedder=embedder,
        entities=schema["node_types"],         
        relations=schema["relationship_types"],  
        prompt_template=PROMPT_TEMPLATE,
        from_pdf=False,
        text_splitter=chunk_splitter,
        perform_entity_resolution=True,
        on_error="IGNORE",
        
    )
    
    return kg_builder_pdf, kg_builder_text

encoder_llm = None
retriever_llm = None
embedder = None
kg_builder_pdf = None
kg_builder_text = None
retriever = None
PROCESS_CONTEXT = False

def init_globals():
    global encoder_llm, retriever_llm, embedder, kg_builder_pdf, kg_builder_text, retriever, neo4j_driver
    
    driver_recreated = ensure_driver_connected()

    if encoder_llm is None or driver_recreated:
        # print("DEBUG PROLOG-GRAPHRAG:Re-initializing pipelines due to missing LLM or new driver...", flush=True)
        encoder_llm, retriever_llm, embedder = initialize_models()
        kg_builder_pdf, kg_builder_text = setup_kg_pipeline(encoder_llm, embedder)
        retriever = create_retriever(neo4j_driver, embedder)

def generate_answer(query, retriever, llm, original_query: str = "") -> dict:
    return generate(llm, retriever, query, original_query=original_query)

def run_pipeline(question: str, fallback: str) -> dict:
    init_globals()
    
    # 1. Clear stale Neo4j data from previous questions to prevent irrelevant retrieval
    # print("DEBUG PROLOG-GRAPHRAG [run_pipeline]: Clearing local data...", flush=True)
    # clear_local_data()
    # print("DEBUG PROLOG-GRAPHRAG [run_pipeline]: Local data cleared. Starting extract_query_and_context...", flush=True)
    
    # 2. Extract query and context from user input
    query, text_context = extract_query_and_context(question)
    # print(f"DEBUG PROLOG-GRAPHRAG [run_pipeline]: extract_query_and_context done. query={repr(query[:80])} | context items={len(text_context) if isinstance(text_context, list) else 'str'}", flush=True)
    
    # 3. OPT3: Only ingest into the KG if the encoder actually found real context
    #    (e.g. a passage-based question). For self-contained MCQs, context is empty —
    #    ingesting the question itself produces barely-useful local chunks (~0.7 score)
    #    while adding a full LLM call + 2s sleep per question. Skip it.
    context_was_extracted = bool(text_context)  # True only if encoder found real facts/passages
    
    if not context_was_extracted:
        # print("DEBUG PROLOG-GRAPHRAG [run_pipeline]: No extracted context (MCQ). Skipping KG ingestion — querying KBPedia directly.", flush=True)
        text_context = [question]  # keep for logging/reference, but don't ingest
    else:
        # print(f"DEBUG PROLOG-GRAPHRAG [run_pipeline]: Starting process_context (KG ingestion) with {len(text_context)} text chunk(s)...", flush=True)
        if PROCESS_CONTEXT:
            _run_async(process_context(neo4j_driver, kg_builder_pdf=kg_builder_pdf, kg_builder_text=kg_builder_text, texts=text_context))
            # print("DEBUG PROLOG-GRAPHRAG [run_pipeline]: process_context done. Sleeping 2s for index update...", flush=True)
        time.sleep(2) # Allow vector index to update
        # print("DEBUG PROLOG-GRAPHRAG [run_pipeline]: Sleep done.", flush=True)

    # print("DEBUG PROLOG-GRAPHRAG [run_pipeline]: Starting generate (retriever + LLM)...", flush=True)
    success = False
    graph_rag = GraphRAG(llm=retriever_llm, retriever=retriever, prompt_template=GRAPHRAG_TEMPLATE if fallback == "prolog-graphrag" else GRAPHRAG_FALLBACK_TEMPLATE)
    retriever_result = []
    try:
        graph_rag_results = graph_rag.search(query, retriever_config={'top_k': 5}, return_context=True)
        retriever_result = graph_rag_results.retriever_result
        # print(f"RESULTS:\n{retriever_result}")
        answer_dict = graph_rag_results.answer
        answer = answer_dict.get("answer", "") if isinstance(answer_dict, dict) else str(answer_dict)
        logprobs = answer_dict.get("logprobs", {}) if isinstance(answer_dict, dict) else {}
        # print(f"ANSWER:\n{answer}")
        # print("DEBUG PROLOG-GRAPHRAG [run_pipeline]: generate done. Returning result.", flush=True)
        success = True
    except Exception as e:
        print(f"ERROR during generation: {e}", flush=True)
        generation_result = {"answer": f"Error during generation: {e}", "retriever_results": []}
    
    return {
        "query": query,
        "text_context": text_context,
        "answer": answer if success else "Error during generation.",
        "logprobs": logprobs if success else [],
        "retriever_results": retriever_result,
    }
    

async def test_process_pdf_context(kg_builder_pdf: SimpleKGPipeline):
    await process_pdf_documents(kg_builder_pdf)
    
    
async def test_process_text_context(kg_builder_text: SimpleKGPipeline, query: str):
    await process_text_context(kg_builder_text)
    
    
def test_extract_query_and_context(question: str):
    query, context = extract_query_and_context(question)
    print(f"Extracted query: {query}")
    print(f"Extracted context: {context}")
    return query, context


def ensure_driver_connected():
    global neo4j_driver
    MAX_RETRIES = 10
    RETRY_DELAY = 30  # seconds between retries
    
    for attempt in range(MAX_RETRIES):
        try:
            if neo4j_driver is not None:
                neo4j_driver.verify_connectivity()
                return False

            # print("DEBUG PROLOG-GRAPHRAG:Initializing new Neo4j driver...", flush=True)
            neo4j_driver = neo4j.GraphDatabase.driver(
                NEO4J_URI, 
                auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
                connection_timeout=10.0, 
                max_connection_lifetime=200, 
                encrypted=False
            )
            neo4j_driver.verify_connectivity()
            # print("DEBUG PROLOG-GRAPHRAG:Neo4j driver initialized and connected.", flush=True)
            return True
        except Exception as e:
            print(f"CRITICAL ERROR: Could not connect to Neo4j (attempt {attempt+1}/{MAX_RETRIES}): {e}", flush=True)
            if neo4j_driver:
                try:
                    neo4j_driver.close()
                except:
                    pass
            neo4j_driver = None
            
            if attempt < MAX_RETRIES - 1:
                print(f"Retrying in {RETRY_DELAY}s...", flush=True)
                import time
                time.sleep(RETRY_DELAY)
            else:
                raise ConnectionError(f"Failed to connect to Neo4j after {MAX_RETRIES} attempts: {e}") from e


def clear_local_data():
    """
    Deletes pipeline-generated nodes/relationships from the database,
    but preserves KBPedia reference concepts which are a static knowledge base.
    """
    ensure_driver_connected()
    print("WARNING: Clearing pipeline data (preserving KBPedia)...")
    try:
        with neo4j_driver.session(database="neo4j") as session:
            session.run("MATCH (n) WHERE NOT n:KBPediaConcept DETACH DELETE n")
    except Exception as e:
        print(f"Error clearing local data: {e}")
    print("Database cleared successfully (KBPedia preserved).")

def main():
    # Uncomment to clear data before running tests
    # clear_local_data() 
    # _run_async(perform_tests())
    pass


if __name__ == "__main__":
    init_globals()
    _run_async(process_context(neo4j_driver, kg_builder_pdf=kg_builder_pdf, kg_builder_text=kg_builder_text, texts=[]))
    print("Initial context processing done. You can now call run_pipeline(question) with your queries.")