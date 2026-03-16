from copy import deepcopy
import os
import sys
import signal
import threading
import time
import logging

from ..llm_config import PROLOG_GENERATOR_NAME, MODEL_NAME, USE_TOGETHER_API, get_openai_client, log_llm_event, retry_with_exponential_backoff

logger = logging.getLogger(__name__)

# Prolog code generation and NL tasks both use the configured model
PROLOG_MODEL = PROLOG_GENERATOR_NAME
NL_MODEL = MODEL_NAME
LLM_TIMEOUT = 120  # seconds per LLM call (2 minutes)

client = get_openai_client()

# ── KV-cache warmup ────────────────────────────────────────────────────────
# Ollama reuses its KV cache when the prefix of a chat request matches a
# previously seen prefix.  Because the GraphRAG step runs the same model just
# before Prolog generation, it evicts the Prolog prefix from the cache.
# warmup_prolog_model() re-primes the cache (system prompt + few-shots) once
# per question so that all retry attempts within that question are fast.
# NOTE: Warmup is Ollama-specific and skipped when using Together AI.
_kv_cache_warmed = False

def warmup_prolog_model():
    """Prime Ollama's KV cache with the static few-shot prefix (once per question)."""
    global _kv_cache_warmed
    if _kv_cache_warmed or USE_TOGETHER_API:
        return
    import ollama
    try:
        from .prolog_config import GENERATOR_LLM_MESSAGES, USE_KV_CACHE
    except ImportError:
        from prolog_graphrag_pipeline.prolog.prolog_config import GENERATOR_LLM_MESSAGES, USE_KV_CACHE
        
    if not USE_KV_CACHE:
        return
        
    try:
        print("[Prolog Warmup] Priming KV cache with few-shot prefix...", flush=True)
        ollama.chat(
            model=PROLOG_MODEL,
            messages=GENERATOR_LLM_MESSAGES + [
                {'role': 'user', 'content': 'Now, process the following:\nContext: A is true.\nUser Question: Is A true?\n'}
            ],
            options={'temperature': 0, 'keep_alive': '20m', 'num_ctx': 4096},
        )
        _kv_cache_warmed = True
        print("[Prolog Warmup] KV cache primed.", flush=True)
    except Exception as e:
        print(f"[Prolog Warmup] Non-fatal warmup failure: {e}", flush=True)

def reset_kv_cache_flag():
    """Call this before each new question so warmup re-runs after GraphRAG evicts the cache."""
    global _kv_cache_warmed
    _kv_cache_warmed = False

def reset_ollama_model():
    """Force-unload the model from Ollama, then verify it reloads successfully with strict timeouts.
    Skipped when using Together AI (no local model to reset).
    """
    if USE_TOGETHER_API:
        return

    import ollama
    
    def run_with_timeout(target_func, timeout=30):
        error_holder = [None]
        result_holder = [None]
        
        def wrapper():
            try:
                result_holder[0] = target_func()
            except Exception as e:
                error_holder[0] = e
                
        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        
        if thread.is_alive():
            raise TimeoutError(f"Operation timed out after {timeout} seconds")
        if error_holder[0]:
            raise error_holder[0]
        return result_holder[0]

    try:
        print("[Ollama Reset] Unloading prolog model to recover from hang...", flush=True)
        run_with_timeout(lambda: ollama.generate(model=PROLOG_MODEL, prompt="", keep_alive=0))
        print("[Ollama Reset] Model unloaded.", flush=True)
    except Exception as e:
        print(f"[Ollama Reset] Warning during unload: {e}", flush=True)

    # Verify the model reloads successfully with a simple ping
    try:
        print("[Ollama Reset] Verifying model reloads...", flush=True)
        test_response = run_with_timeout(
            lambda: ollama.chat(
                model=PROLOG_MODEL,
                messages=[{'role': 'user', 'content': 'Say OK'}],
                options={'temperature': 0, 'keep_alive': '20m'},
            )
        )
        reply = test_response.get('message', {}).get('content', '').strip()
        print(f"[Ollama Reset] Model reloaded successfully. Ping reply: {reply[:50]}", flush=True)
    except Exception as e:
        print(f"[Ollama Reset] WARNING: Model failed to reload: {e}", flush=True)

def generate(prompt: str, flag: str) -> dict:
    if flag not in ["prolog", "explanation", "q"]:
        raise ValueError(f"Flag {flag} is invalid. Only 'prolog', 'explanation', and 'q' are accepted.")
    
    return generate_response(prompt=prompt, flag=flag)

    
def generate_response(prompt: str, flag: str) -> dict:
    from .prolog_config import GENERATOR_LLM_MESSAGES, EXPLAINER_LLM_MESSAGES, USE_KV_CACHE
    
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

    if USE_KV_CACHE:
        # KV Caching ENABLED: Send as distinct objects to trigger prefix caching in Together/Ollama
        llm_messages = base_messages + [{'role': 'user', 'content': prompt}]
    else:
        # KV Caching DISABLED: Flatten context into a single "raw" user prompt block.
        # Useful for models that prefer single-turn instructions or when benchmarking linear performance.
        flattened_context = ""
        for msg in base_messages:
            role = msg.get('role', 'system').upper()
            content = msg.get('content', '')
            flattened_context += f"<{role}>\n{content}\n</{role}>\n\n"
        
        dynamic_prompt = f"{flattened_context}\nPlease answer the following query based on past instructions:\n{prompt}"
        llm_messages = [{'role': 'user', 'content': dynamic_prompt}]

    # Use a thread to enforce a hard timeout on the LLM call
    result_holder = [None]
    error_holder = [None]

    def _call_llm():
        try:
            # Log the outgoing prompt
            logger.debug(f"PROLOG PROMPT ({flag.upper()}): {dynamic_prompt if 'dynamic_prompt' in locals() else '(KV-cache mode)'}")
            
            start_time = time.perf_counter()
            
            # Wrap with exponential backoff to shield evaluation from server hiccups
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
            
            # Log the response content
            if response and response.choices:
                content = response.choices[0].message.content
                logger.debug(f"PROLOG RESPONSE ({flag.upper()}): {content[:500]}")
        except Exception as e:
            error_holder[0] = e

    thread = threading.Thread(target=_call_llm, daemon=True)
    thread.start()
    thread.join(timeout=LLM_TIMEOUT)

    if thread.is_alive():
        # LLM is hung — reset and raise
        print(f"[LLM TIMEOUT] LLM call exceeded {LLM_TIMEOUT}s. Resetting model...", flush=True)
        reset_ollama_model()
        raise TimeoutError(f"LLM call timed out after {LLM_TIMEOUT}s")

    if error_holder[0]:
        print(f"Error during LLM interaction: {error_holder[0]}")
        return {}

    response = result_holder[0]
    if response is None:
        return None

    try:
        answer['text_answer'] = response.choices[0].message.content
        answer['logprobs'] = None
        return answer
    except Exception as e:
        print(f"Error during LLM interaction: {e}")
        return {}
    
# import ollama
# response = ollama.chat(
#             model='llama3:instruct',
#             messages=[{'role': 'user', 'content': "What is the Riemann sum definition of the definite integral?"}],
#             options={
#                 'temperature': 0  
#             },
#             logprobs=True     
#         )
    
# print(response['message']['content'])