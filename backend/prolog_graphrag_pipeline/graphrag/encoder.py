from neo4j_graphrag.experimental.components.text_splitters.fixed_size_splitter import FixedSizeSplitter
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
import os
import sys
import glob
from .config import DOC_PATH, ENCODER_SYSTEM_PROMPT, ENCODER_FEW_SHOT_EXAMPLES

# Ensure project root is on the path so llm_config can be imported
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from llm_config import MODEL_NAME, get_openai_client, log_llm_event, retry_with_exponential_backoff

import json
import asyncio
import time

client = get_openai_client()

# Stateless message template
BASE_OLLAMA_MESSAGES = [
            {'role': 'system', 'content': ENCODER_SYSTEM_PROMPT},
            
        ] + ENCODER_FEW_SHOT_EXAMPLES

from typing import Optional

def generate_with_ollama(messages) -> Optional[str]: 
    try:
        start_time = time.perf_counter()
        
        # Wrap with exponential backoff
        invoke_func = retry_with_exponential_backoff(client.chat.completions.create)
        
        response = invoke_func(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        duration = time.perf_counter() - start_time
        log_llm_event("ENCODER_EXTRACT", duration=duration)
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error during LLM interaction ({MODEL_NAME}): {e}")
        return {}
    
    
def extract_query_and_context(question: str) -> tuple[str, str]:
    most_recent_error = None
    
    current_messages = list(BASE_OLLAMA_MESSAGES)

    for i in range(5):
        try:
            prompt_content = question
            if most_recent_error:
                prompt_content += f"\nYour latest output had error/s. Fix them according to the following error message:\n{most_recent_error}"
            

            turn_message = {'role': 'user', 'content': prompt_content}
            
            current_messages.append(turn_message)
            
            response = generate_with_ollama(current_messages)
            safe_response = str(response).encode('ascii', 'replace').decode('ascii')
            # print("LLM Response:", safe_response) # verbose
            
            if response is None:
                raise ValueError("Failed to get a response from the LLM.")
            
            try:
                extracted_data = json.loads(response)
                # print(f"DEBUG PROLOG-GRAPHRAG:Parsed JSON: {extracted_data}")

                if not isinstance(extracted_data, dict):
                    raise ValueError(f"Expected dict, got {type(extracted_data)}")

                # Normalize keys (handle case variations)
                data = {k.lower(): v for k, v in extracted_data.items()}
                # print(f"DEBUG PROLOG-GRAPHRAG:Normalized keys: {list(data.keys())}")
                
                # Map alternative keys to standard keys
                if "cleaned_query" in data and "question" not in data:
                    data["question"] = data["cleaned_query"]
                if "extracted_context" in data and "context" not in data:
                    data["context"] = data["extracted_context"]
                
                if "question" not in data or "context" not in data:
                     raise ValueError(f"Missing required keys 'question' or 'context' in JSON response. Keys found: {list(data.keys())}")
                
                safe_query = str(data.get('question', 'N/A')).encode('ascii', 'replace').decode('ascii')
                # print(f"DEBUG PROLOG-GRAPHRAG:EXTRACTED QUERY: {safe_query}")
                # print(f"DEBUG PROLOG-GRAPHRAG:EXTRACTED CONTEXT (Len: {len(data.get('context', []))}): {data.get('context', [])}")
                return data["question"], data["context"]
            except json.JSONDecodeError as e:
                print(f"JSON decoding error: {e}")
                current_messages.append({'role': 'assistant', 'content': response})
                most_recent_error = f"JSON Decode Error: {e}"
                
        except Exception as e:
            print(f"DEBUG PROLOG-GRAPHRAG:Exception in loop: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            most_recent_error = str(e)
            if i < 4:
                time.sleep(2)  # Wait before retry
            
    raise ValueError(f"Failed to extract query and context after 5 retries. Last error: {most_recent_error}")

async def process_pdf_documents(kg_builder_pdf: Optional[SimpleKGPipeline]):
    paths = glob.glob(os.path.join(DOC_PATH, "*.pdf"))
    
    for path in paths:
        print(f"Processing document: {path}")
        pdf_result = await kg_builder_pdf.run_async(file_path=path)
        print(f"Document processed: {pdf_result}")

async def process_text_context(kg_builder_text: SimpleKGPipeline, texts: list[str]):
    for text in texts:
        print(f"Processing text context: {text}")
        text_result = await kg_builder_text.run_async(text=text)
        print(f"Text context processed: {text_result}")

async def process_markdown_documents(kg_builder_text: SimpleKGPipeline):
    print(DOC_PATH)
    paths = glob.glob(os.path.join(DOC_PATH, "*.md"))
    print("PATHS: ", paths)
    for path in paths:
        markdown_text = ""
        with open(path, "r", encoding="utf-8") as f:
            markdown_text = f.read()
        print(f"Processing markdown document: {path}")
        text_result = await kg_builder_text.run_async(text=markdown_text)
        print(f"Text context processed: {text_result}")

async def process_context(driver, kg_builder_pdf, kg_builder_text, texts):
    await asyncio.gather(process_markdown_documents(kg_builder_text))
    # if texts:
    #     await asyncio.gather(process_text_context(kg_builder_text, texts))
        
    # driver.execute_query("""
    #     MATCH (n) 
    #     WHERE n.subgraph IS NULL 
    #     AND coalesce(n.source, '') <> 'KBPedia' 
    #     // Also exclude by label if KBPedia uses a specific one, e.g., AND NOT n:KBPediaNode
    #     SET n.subgraph = 'prolog-graphrag'
    # """)
        
# query, context = extract_query_and_context("Francis is a student studying computer science. Like any CS major, he is interested in machine learning and artificial intelligence. What courses should he take to specialize in these fields?")
# print("Extracted Query:", query)
# print("\nExtracted Context:", context)