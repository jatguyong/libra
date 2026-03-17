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


CLASSIFIER_SYSTEM_PROMPT = """You are a question type classifier. Given a user question, classify it into exactly one of three types:

- MCQ: The question explicitly lists multiple-choice options labelled A, B, C, D (or A., B., C., D. or A) B) C) D)).
- Binary: The question asks whether a specific condition is true or false, can be answered with yes/no.
- Freeform: Any other question — explanatory, conceptual, comparative, "what is", "how does", "why", etc.

Respond with ONLY one word: MCQ, Binary, or Freeform.
Do not explain. Do not add punctuation. Output exactly one word."""


def classify_question_type(question: str) -> str:
    """
    Fast LLM classifier: returns 'mcq', 'binary', or 'freeform'.
    Falls back to regex detection if the LLM call fails or returns unexpected output.
    """
    import re as _re

    # Fast regex shortcut: if the question has A. / B. / A) / B) options it's MCQ
    if _re.search(r'\b[A-D][.)]\s', question):
        logger.info("[QuestionClassifier] Regex detected: MCQ")
        return "mcq"

    try:
        invoke_func = retry_with_exponential_backoff(client.chat.completions.create)
        response = invoke_func(
            model=NL_MODEL,
            messages=[
                {"role": "user", "content": CLASSIFIER_SYSTEM_PROMPT},
                {"role": "user", "content": f"Question: {question}"},
            ],
            temperature=0,
            max_tokens=5,
            timeout=30,
        )
        raw = response.choices[0].message.content.strip().lower()
        logger.info(f"[QuestionClassifier] LLM response: {repr(raw)}")
        if "mcq" in raw or "multiple" in raw or "choice" in raw:
            return "mcq"
        if "binary" in raw or "true" in raw or "false" in raw or "yes" in raw or "no" in raw:
            return "binary"
        return "freeform"
    except Exception as e:
        logger.warning(f"[QuestionClassifier] LLM call failed ({e}), defaulting to 'freeform'")
        return "freeform"


def generate(prompt: str, flag: str, question_type: str = "freeform") -> dict:
    if flag not in ["prolog", "explanation", "q"]:
        raise ValueError(f"Flag {flag} is invalid. Only 'prolog', 'explanation', and 'q' are accepted.")
    
    return generate_response(prompt=prompt, flag=flag, question_type=question_type)

    
def generate_response(prompt: str, flag: str, question_type: str = "freeform") -> dict:
    from .prolog_config import build_generator_messages, EXPLAINER_LLM_MESSAGES
    
    answer = dict()
    
    # Select model based on flag: code-tuned for Prolog, NL model for everything else
    if flag == "prolog":
        model = PROLOG_MODEL
        # Dynamically build messages with only the matching few-shot examples
        base_messages = build_generator_messages(question_type)
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