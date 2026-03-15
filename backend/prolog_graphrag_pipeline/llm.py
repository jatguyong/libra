import sys
import os
import json
from typing import Literal
from pydantic import BaseModel

from .llm_config import MODEL_NAME, get_openai_client
from .config import FALLBACK_MESSAGES

from .config import LLM_SYSTEM_PROMPT, LLM_MESSAGES, LLM_SYSTEM_PROMPT_FALLBACK
from .prompt_reconstructor import reconstruct_prompt

from typing import Optional, Union, List

client = get_openai_client()

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
    
def decide_fallback(question: str):
    response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=FALLBACK_MESSAGES + [{"role": "user", "content": question}],
            temperature=0.7,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "routing_schema",
                    "strict": True,
                    "schema": RoutingResponse.model_json_schema()
                }
            }
        )
    content_str = response.choices[0].message.content
    try:
        data = json.loads(content_str)
    except json.JSONDecodeError:
        # Handle cases where the model might still fail or return an empty string
        print("Failed to decode JSON:", content_str)
        return False
    return data["route_to"] # True means fallback to GraphRAG


def generate(question: str, retrieved_context: Optional[str], explainer_output: Optional[str] | None, flag: str, sample_mode: bool = False, fallback: str = "prolog-graphrag", status_callback=None) -> Union[dict, List[dict]]:
    if fallback != "prolog-graphrag":
        final_prompt = question
        messages = LLM_SYSTEM_PROMPT_FALLBACK + [{"role": "user", "content": final_prompt}]
    else:
        final_prompt = reconstruct_prompt(question=question, retrieved_context=retrieved_context, explainer_output=explainer_output, flag=flag)
        messages = LLM_MESSAGES + [{"role": "user", "content": final_prompt}]
        
    print(f"FINAL PROMPT:\n{final_prompt}")
    
    def _do_call_llm():
        if status_callback and fallback == "prolog-graphrag":
            status_callback({"type": "step", "step": 8})
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.3,
            logprobs=True
        )
        answer = dict()
        answer['text_answer'] = response.choices[0].message.content
        answer['logprobs'] = response.choices[0].logprobs.content
        return answer

    def _call_llm():
        from .llm_config import retry_with_exponential_backoff
        try:
            func = retry_with_exponential_backoff(_do_call_llm)
            return func()
        except Exception as e:
            err_msg = f"Error during synthesis LLM interaction ({MODEL_NAME}): {e}"
            print(err_msg)
            try:
                with open("debug_synthesis_llm.txt", "a", encoding="utf-8") as f:
                    f.write(err_msg + f"\nPROMPT LENGTH: {len(final_prompt)}\n\n")
            except:
                pass
            raise

    if sample_mode:
        sequences = []
        for i in range(5):
            try:
                sequences.append(_call_llm())
            except Exception as e:
                print(f"Error during LLM interaction ({MODEL_NAME}): {e}")
                return {}
        return sequences
    else:
        try:
            return _call_llm()
        except Exception as e:
            print(f"Error during LLM interaction ({MODEL_NAME}): {e}")
            return {}