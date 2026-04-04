"""LLM interaction layer for the pipeline's routing and answer-generation steps.

Key functions:
  - ``decide_fallback(question)`` — classifies a question as needing
    Prolog-GraphRAG, plain GraphRAG, or direct LLM synthesis.
  - ``generate(...)`` — produces the final natural-language answer by
    combining retrieved context, Prolog explanations, and log-probabilities.
  - ``create_system_messages(fallback)`` — selects the appropriate
    few-shot message template for the current routing path.
"""
import sys
import os
import json
import logging
import traceback
from typing import Literal, Optional, Union, List

from pydantic import BaseModel

from .llm_config import MODEL_NAME, get_openai_client, retry_with_exponential_backoff
from .config import FALLBACK_MESSAGES, LLM_SYSTEM_PROMPT, LLM_MESSAGES, LLM_SYSTEM_PROMPT_FALLBACK
from .prompt_reconstructor import reconstruct_prompt

logger = logging.getLogger(__name__)

# Lazy singleton — client is created on first use so an absent API key
# raises at call time, not at import time (which causes startup-crash loops).
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = get_openai_client()
    return _client


class Reasoning(BaseModel):
    reasoning: str

class Checklist(BaseModel):
    requires_external_context_or_retrieval: Literal["pass", "fail"]
    involves_reasoning_or_rules: Literal["pass", "fail"]
    is_beyond_simple_general_knowledge: Literal["pass", "fail"]

class RoutingResponse(BaseModel):
    reasoning: Reasoning
    checklist: Checklist
    route_to: Literal["prolog-graphrag", "graphrag", "tuned"]


def decide_fallback(question: str) -> str:
    """Ask the LLM to route the question to the appropriate pipeline path.

    Returns one of: "prolog-graphrag", "graphrag", "tuned".
    Falls back to "tuned" on any parsing failure so the app never crashes.
    """
    response = _get_client().chat.completions.create(
        model=MODEL_NAME,
        messages=FALLBACK_MESSAGES + [{"role": "user", "content": question}],
        temperature=0.7,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "routing_schema",
                "strict": True,
                "schema": RoutingResponse.model_json_schema(),
            },
        },
    )
    content_str = response.choices[0].message.content
    try:
        data = json.loads(content_str)
    except json.JSONDecodeError:
        logger.warning("Router JSON decode failed, falling back to tuned. Raw: %s", content_str)
        return "tuned"
    return data.get("route_to", "tuned")


def generate(
    question: str,
    retrieved_context: Optional[str],
    explainer_output: Optional[str],
    flag: str,
    sample_mode: bool = False,
    fallback: str = "prolog-graphrag",
    status_callback=None,
) -> Union[dict, List[dict]]:
    """Generate a final answer using the synthesis LLM.

    Returns a single dict in normal mode, or a list of dicts in sample_mode.
    """
    if fallback != "prolog-graphrag":
        final_prompt = question
        messages = LLM_SYSTEM_PROMPT_FALLBACK + [{"role": "user", "content": final_prompt}]
    else:
        final_prompt = reconstruct_prompt(
            question=question, retrieved_context=retrieved_context,
            explainer_output=explainer_output, flag=flag,
        )
        messages = LLM_MESSAGES + [{"role": "user", "content": final_prompt}]

    logger.debug("Final prompt:\n%s", final_prompt)

    if status_callback:
        if fallback == "prolog-graphrag":
            status_callback({"type": "step", "step": 8})
            status_callback({"type": "thought", "step": 8, "message": "I mapped your question, the context, and the logical proof into a strict prompt template."})
            status_callback({"type": "step", "step": 9})
            if sample_mode:
                status_callback({"type": "thought", "step": 9, "message": f"I'm generating 4 more output sequences to calculate semantic entropy based on {len(final_prompt)} characters of processed context and proof..."})
            else:
                status_callback({"type": "thought", "step": 9, "message": f"I'm synthesizing the final response by merging {len(final_prompt)} characters of processed evidence and logic proof..."})
        elif fallback == "tuned":
            status_callback({"type": "thought", "step": 2, "message": "I'm formulating my final conversational response..."})

    def _do_call_llm():
        response = _get_client().chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.3,
            logprobs=True,
        )
        answer = {}
        answer['text_answer'] = response.choices[0].message.content

        # Extract logprobs — handle both OpenAI and Together AI formats
        raw_logprobs = response.choices[0].logprobs
        answer['logprobs'] = []
        if raw_logprobs:
            if raw_logprobs.content:
                # OpenAI format: logprobs.content is a list of token logprob objects
                answer['logprobs'] = [
                    {"token": lp.token, "logprob": lp.logprob}
                    if hasattr(lp, 'token') else lp
                    for lp in raw_logprobs.content
                ]
            elif hasattr(raw_logprobs, 'tokens') and hasattr(raw_logprobs, 'token_logprobs') and raw_logprobs.tokens:
                # Together AI format: tokens + token_logprobs as parallel arrays
                answer['logprobs'] = [
                    {"token": tok, "logprob": lp}
                    for tok, lp in zip(raw_logprobs.tokens, raw_logprobs.token_logprobs)
                ]
        return answer

    def _call_llm():
        try:
            func = retry_with_exponential_backoff(_do_call_llm)
            return func()
        except Exception as e:
            logger.error("Synthesis LLM error (%s): %s | prompt length: %d", MODEL_NAME, e, len(final_prompt))
            raise

    if sample_mode:
        sequences = []
        for i in range(5):
            try:
                sequences.append(_call_llm())
            except Exception as e:
                logger.error("Sample %d failed (%s): %s", i, MODEL_NAME, e)
                # Continue collecting the remaining samples; only bail if all fail
        if not sequences:
            return []  # every sample failed
        return sequences
    else:
        try:
            return _call_llm()
        except Exception as e:
            logger.error("LLM call failed (%s): %s", MODEL_NAME, e)
            return {}