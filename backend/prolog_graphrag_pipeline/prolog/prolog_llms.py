from copy import deepcopy
import os
import sys
import signal
import threading
import time
import logging

from ..llm_config import PROLOG_GENERATOR_NAME, MODEL_NAME, get_openai_client, log_llm_event, retry_with_exponential_backoff

logger = logging.getLogger(__name__)

# Prolog code generation and NL tasks both use the configured model
PROLOG_MODEL = PROLOG_GENERATOR_NAME
NL_MODEL = MODEL_NAME
LLM_TIMEOUT = 120  # seconds per LLM call (2 minutes)

client = get_openai_client()


def generate(prompt: str, flag: str) -> dict:
    if flag not in ["prolog", "explanation", "q"]:
        raise ValueError(f"Flag {flag} is invalid. Only 'prolog', 'explanation', and 'q' are accepted.")
    
    return generate_response(prompt=prompt, flag=flag)

    
def generate_response(prompt: str, flag: str) -> dict:
    from .prolog_config import GENERATOR_LLM_MESSAGES, EXPLAINER_LLM_MESSAGES
    
    answer = dict()
    
    # Select model based on flag: code-tuned for Prolog, NL model for everything else
    if flag == "prolog":
        model = PROLOG_MODEL
        base_messages = GENERATOR_LLM_MESSAGES
        temperature = 0
    elif flag == "explanation":
        model = NL_MODEL
        base_messages = EXPLAINER_LLM_MESSAGES
        temperature = 0.2
    elif flag == "q":
        model = NL_MODEL
        base_messages = []
        temperature = 0
    else:
        raise ValueError(f"Flag {flag} is invalid. Only 'prolog', 'explanation', and 'q' are accepted.")

    # Send few-shot prefix as distinct message objects for provider-side KV cache reuse
    llm_messages = base_messages + [{'role': 'user', 'content': prompt}]

    # Use a thread to enforce a hard timeout on the LLM call
    result_holder = [None]
    error_holder = [None]

    def _call_llm():
        try:
            start_time = time.perf_counter()
            
            invoke_func = retry_with_exponential_backoff(client.chat.completions.create)
            
            response = invoke_func(
                model=model,
                messages=llm_messages,
                temperature=float(temperature),
                timeout=LLM_TIMEOUT,
                max_tokens=2048,
            )
            duration = time.perf_counter() - start_time
            log_llm_event(f"PROLOG_{flag.upper()}", duration=duration)
            result_holder[0] = response
            
            if response and response.choices:
                content = response.choices[0].message.content
                logger.debug("PROLOG RESPONSE (%s): %s", flag.upper(), content[:500])
        except Exception as e:
            error_holder[0] = e

    thread = threading.Thread(target=_call_llm, daemon=True)
    thread.start()
    thread.join(timeout=LLM_TIMEOUT)

    if thread.is_alive():
        logger.error("[LLM TIMEOUT] Call exceeded %ds.", LLM_TIMEOUT)
        raise TimeoutError(f"LLM call timed out after {LLM_TIMEOUT}s")

    if error_holder[0]:
        logger.error("LLM interaction error: %s", error_holder[0])
        return {}

    response = result_holder[0]
    if response is None:
        return None

    try:
        answer['text_answer'] = response.choices[0].message.content
        answer['logprobs'] = None
        return answer
    except Exception as e:
        logger.error("LLM response parsing error: %s", e)
        return {}