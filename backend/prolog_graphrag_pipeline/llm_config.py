"""
Centralized LLM provider configuration.

All pipeline modules use the Together AI cloud API via the
standard `openai` Python package.
"""

import os
import logging
import time
import random
import httpx
from openai import OpenAI, APIConnectionError, APITimeoutError, InternalServerError, RateLimitError, APIError, APIStatusError

logger = logging.getLogger(__name__)


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
                if isinstance(e, APIStatusError) and e.status_code in [401, 403, 404]:
                    raise e

                last_exception = e
                if attempt == max_retries:
                    break
                
                actual_sleep = sleep_time
                if jitter:
                    actual_sleep += random.uniform(0, 1)
                
                log_llm_event(f"RETRY_BACKOFF_ATTEMPT_{attempt+1}", error=f"Waiting {actual_sleep:.2f}s after error: {type(e).__name__}")
                logger.warning("[LLM BACKOFF] Attempt %d failed (%s). Retrying in %.2fs...", attempt + 1, type(e).__name__, actual_sleep)
                
                time.sleep(actual_sleep)
                sleep_time *= backoff_factor
            except Exception as e:
                raise e
        
        raise last_exception
    return wrapper

# Model Configuration
BASE_URL = "https://api.together.xyz/v1"
RAGAS_MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
ENCODER_MODEL_NAME = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
MODEL_NAME = "meta-llama/Meta-Llama-3-8B-Instruct-Lite"
PROLOG_GENERATOR_NAME = "deepseek-ai/DeepSeek-V3.1"
EMBED_MODEL = "intfloat/multilingual-e5-large-instruct"
EMBED_DIM = 1024


def log_llm_event(event_type: str, duration: float = None, error: str = None):
    """Log LLM events for performance tracking."""
    log_msg = f"[LLM_EVENT] {event_type}"
    if duration is not None:
        log_msg += f" | LATENCY: {duration:.4f}s"
    if error:
        log_msg += f" | ERROR: {error}"
    logger.info(log_msg)

def get_openai_client() -> OpenAI:
    """Return a configured OpenAI client for the active provider.

    Reads and validates TOGETHER_API_KEY here (not at import time) so a
    missing key produces a clear error on the first API call rather than
    crashing the entire process during startup.
    """
    api_key = os.environ.get("TOGETHER_API_KEY", "")
    if not api_key:
        raise EnvironmentError(
            "TOGETHER_API_KEY environment variable is not set. "
            "Export it before running:  set TOGETHER_API_KEY=your_key"
        )
    http_client = httpx.Client(timeout=120.0)
    return OpenAI(base_url=BASE_URL, api_key=api_key, http_client=http_client, max_retries=0)
