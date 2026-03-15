from neo4j_graphrag.experimental.components.text_splitters.fixed_size_splitter import FixedSizeSplitter
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
import os
import sys
import glob
from .config import DOC_PATH, ENCODER_SYSTEM_PROMPT, ENCODER_FEW_SHOT_EXAMPLES

from ..llm_config import MODEL_NAME, get_openai_client, log_llm_event, retry_with_exponential_backoff

import json
import asyncio
import time

client = get_openai_client()

# Stateless message template
BASE_OLLAMA_MESSAGES = [
            {'role': 'user', 'content': ENCODER_SYSTEM_PROMPT},
            
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

async def process_pdf_documents(
    kg_builder_pdf: Optional[SimpleKGPipeline], 
    file_paths: list[str] = None,
    max_concurrent: int = 3,
):
    """Process PDF documents into the knowledge graph with parallel LLM calls.
    
    Args:
        kg_builder_pdf: The SimpleKGPipeline configured with from_pdf=True.
        file_paths: Optional list of specific file paths to process. 
                    If None, globs all PDFs in DOC_PATH.
        max_concurrent: Max concurrent documents to process at once.
    
    Returns:
        List of dicts with file path, result, and timing info.
    """
    import time as _time
    import asyncio
    
    if file_paths is None:
        file_paths = glob.glob(os.path.join(DOC_PATH, "*.pdf"))
    
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def _process_one(path: str) -> dict:
        async with semaphore:
            print(f"[INGEST] Processing: {os.path.basename(path)}", flush=True)
            start = _time.perf_counter()
            try:
                pdf_result = await kg_builder_pdf.run_async(file_path=path)
                duration = _time.perf_counter() - start
                print(f"[INGEST] Done in {duration:.2f}s: {os.path.basename(path)}", flush=True)
                return {"file": path, "result": str(pdf_result), "duration_s": round(duration, 2), "status": "done"}
            except Exception as e:
                duration = _time.perf_counter() - start
                print(f"[INGEST] Error after {duration:.2f}s on {os.path.basename(path)}: {e}", flush=True)
                return {"file": path, "error": str(e), "duration_s": round(duration, 2), "status": "error"}
    
    if len(file_paths) == 1:
        # Single file — run directly (no parallelism overhead)
        results = [await _process_one(file_paths[0])]
    else:
        # Multiple files — process concurrently
        print(f"[INGEST] Processing {len(file_paths)} PDFs (max {max_concurrent} concurrent)...", flush=True)
        tasks = [_process_one(path) for path in file_paths]
        results = await asyncio.gather(*tasks)
        results = list(results)
    
    return results

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