"""
Centralized LLM provider configuration.

Toggle USE_TOGETHER_API to switch every pipeline module between
a local Ollama instance and the Together AI cloud API.

Both providers are accessed through the standard `openai` Python package.
"""

import os
from openai import OpenAI
import httpx
import logging

import time
import random
import httpx
from openai import OpenAI, APIConnectionError, APITimeoutError, InternalServerError, RateLimitError, APIError, APIStatusError

# ── Provider Toggle ──────────────────────────────────────────────────────────
# True  → Together AI  (cloud)
# False → Ollama       (local, http://localhost:11434)
USE_TOGETHER_API = True

def retry_with_exponential_backoff(
    func,
    max_retries=5,
    initial_sleep=1,
    backoff_factor=2,
    jitter=True
):
    """Retries a function with exponential backoff for LLM API calls."""
    def wrapper(*args, **kwargs):
        sleep_time = initial_sleep
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except (APITimeoutError, APIConnectionError, InternalServerError, RateLimitError, APIError, APIStatusError) as e:
                # Also check for specific status codes if it's an APIStatusError
                if isinstance(e, APIStatusError) and e.status_code in [401, 403, 404]:
                    # These are usually not retryable (Auth/Permission/NotFound)
                    raise e

                last_exception = e
                if attempt == max_retries:
                    break
                
                # Calculate sleep duration
                actual_sleep = sleep_time
                if jitter:
                    actual_sleep += random.uniform(0, 1)
                
                log_llm_event(f"RETRY_BACKOFF_ATTEMPT_{attempt+1}", error=f"Waiting {actual_sleep:.2f}s after error: {type(e).__name__}")
                print(f"  > [LLM BACKOFF] Attempt {attempt+1} failed ({type(e).__name__}). Retrying in {actual_sleep:.2f}s...", flush=True)
                
                time.sleep(actual_sleep)
                sleep_time *= backoff_factor
            except Exception as e:
                # For non-retriable exceptions, raise immediately
                raise e
        
        raise last_exception
    return wrapper

# ── Model / Endpoint Configuration ──────────────────────────────────────────
ENABLE_LLAMA_3 = True
USE_OPENAI_API = True
if USE_TOGETHER_API:
    BASE_URL = "https://api.together.xyz/v1"
    API_KEY = os.environ.get("TOGETHER_API_KEY", "")
    RAGAS_MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    ENCODER_MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    MODEL_NAME = "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo" if not ENABLE_LLAMA_3 else "meta-llama/Meta-Llama-3-8B-Instruct-Lite"
    PROLOG_GENERATOR_NAME = "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"
    EMBED_MODEL = "intfloat/multilingual-e5-large-instruct"
    EMBED_DIM = 1024
    if not API_KEY:
        raise EnvironmentError(
            "TOGETHER_API_KEY environment variable is not set. "
            "Export it before running:  set TOGETHER_API_KEY=your_key"
        )
else:
    BASE_URL = "http://localhost:11434/v1"
    API_KEY = "ollama"          # dummy key required by the openai library
    MODEL_NAME = "llama3:instruct"
    EMBED_MODEL = "llama3:instruct"
    EMBED_DIM = 4096


def log_llm_event(event_type: str, duration: float = None, error: str = None):
    """Log LLM events to debug.txt for performance tracking."""
    log_msg = f"\n[LLM_EVENT] {event_type}"
    if duration is not None:
        log_msg += f" | LATENCY: {duration:.4f}s"
    if error:
        log_msg += f" | ERROR: {error}"
    
    try:
        with open("debug.txt", "a", encoding="utf-8") as f:
            f.write(log_msg + "\n")
    except:
        pass

def get_openai_client() -> OpenAI:
    """Return a configured OpenAI client for the active provider."""
    # Use explicit httpx client with timeout to prevent silent hangs
    # Increased to 120s for stability with Together AI Turbo models
    http_client = httpx.Client(timeout=120.0)
    return OpenAI(base_url=BASE_URL, api_key=API_KEY, http_client=http_client, max_retries=0)
