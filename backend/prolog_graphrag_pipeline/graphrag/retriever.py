from typing import List, Any
import time
import asyncio
import json
import re
import types
import logging

logger = logging.getLogger(__name__)

from neo4j.exceptions import ServiceUnavailable, AuthError
from langchain_core.documents import Document

from neo4j_graphrag.retrievers.base import Retriever
from neo4j_graphrag.retrievers import HybridRetriever
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.generation.prompts import RagTemplate
from neo4j_graphrag.types import RetrieverResult, RetrieverResultItem

from .config import RETRIEVAL_QUERY, RETRIEVER

# ... (db health check omitted)

# ... (create_yago_index omitted)

# ... (create_retriever omitted)

def check_db_health(driver):
    """Verifies the driver can connect to Neo4j."""
    try:
        driver.verify_connectivity()
        logger.info("Neo4j driver connected. Pre-flight check passed.")
        return True
    except (ServiceUnavailable, AuthError) as e:
        logger.error("Pre-flight check failed: %s", e)
        return False

def create_indexes(driver):
    from ..llm_config import EMBED_DIM
    embedding_dimension = EMBED_DIM

    driver.execute_query(f"""
        CREATE VECTOR INDEX documentsVectorIndex IF NOT EXISTS
        FOR (n:Chunk) ON (n.embedding)
        OPTIONS {{indexConfig: {{
          `vector.dimensions`: {embedding_dimension},
          `vector.similarity_function`: 'cosine'
        }}}}
    """, database_="neo4j")
    
    driver.execute_query("""
        CREATE FULLTEXT INDEX documentsFulltextIndex IF NOT EXISTS 
        FOR (n:Chunk) ON EACH [n.text]
    """, database_="neo4j")

def wait_for_indexes(driver, timeout=30):
    target_indexes = ['documentsVectorIndex', 'documentsFulltextIndex']
    start_time = time.time()
    
    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"Indexes failed to go ONLINE within {timeout} seconds.")
            
        records, _, _ = driver.execute_query(
            "SHOW INDEXES YIELD name, state WHERE name IN $names",
            names=target_indexes,
            database_="neo4j"
        )
        
        states = [record["state"] for record in records]
        if len(states) == 2 and all(s == "ONLINE" for s in states):
            break
            
        elapsed = int(time.time() - start_time)
        time.sleep(2)

def _sanitize_lucene_query(query_text: str) -> str:
    """Escape Lucene special characters to prevent query parse errors."""
    # Lucene reserved chars: + - && || ! ( ) { } [ ] ^ " ~ * ? : \ /
    special_chars = r'+-&|!(){}[]^"~*?:\/'
    sanitized = []
    for ch in query_text:
        if ch in special_chars:
            sanitized.append(f'\\{ch}')
        else:
            sanitized.append(ch)
    return ''.join(sanitized)

def patched_hybrid_search(self, query_text, top_k=8, **kwargs):
    safe_query = _sanitize_lucene_query(query_text)
    original_query = kwargs.pop("original_query", "")
    use_global_kg = kwargs.pop("use_global_kg", False)
    status_callback = kwargs.pop("status_callback", None)
    all_items = []
    
    # --- KBPedia Global Knowledge Graph Search ---
    if use_global_kg:
        try:
            if not hasattr(self, '_kbpedia_retriever'):
                from .kbpedia_retriever import KBPediaRetriever
                from .neo4j_manager import get_driver
                # HybridRetriever stores driver as self.driver
                kb_driver = getattr(self, 'driver', None) or get_driver()
                # Get the LLM from graphrag_driver globals
                kb_llm = getattr(self, 'llm', None)
                self._kbpedia_retriever = KBPediaRetriever(driver=kb_driver, llm=kb_llm, top_k=top_k)
            
            kb_result = self._kbpedia_retriever.search(
                query_text, 
                top_k=top_k, 
                original_query=original_query, 
                status_callback=status_callback
            )
            if kb_result and kb_result.items:
                all_items.extend(kb_result.items)
                print(f"DEBUG PROLOG-GRAPHRAG:[Hybrid] KBPedia returned {len(kb_result.items)} items.", flush=True)
                if status_callback:
                    status_callback({"type": "step", "step": 3})
                    status_callback({"type": "thought", "step": 3, "message": f"I checked the Global Knowledge Graph (KBPedia) and found {len(kb_result.items)} relevant definition/fact nodes."})
        except Exception as e:
            print(f"DEBUG PROLOG-GRAPHRAG:[Hybrid] KBPedia search error: {e}", flush=True)
    
    # 1. Main query search (local documents)
    res_main = self._original_search(query_text=safe_query, top_k=top_k, **kwargs)
    raw_local_count = 0
    if res_main and res_main.items:
        all_items.extend(res_main.items)
        raw_local_count += len(res_main.items)
        
    # 2. MCQ choices search
    mcq_choices = re.findall(r'\b[A-D][.)]\s*(.+)', original_query)
    if mcq_choices:
        print(f"DEBUG PROLOG-GRAPHRAG:[LocalDocs Hybrid] Extracted {len(mcq_choices)} MCQ choices for independent search.", flush=True)
        if status_callback:
            status_callback({"type": "step", "step": 3})
            status_callback({"type": "thought", "step": 3, "message": f"I extracted {len(mcq_choices)} multiple-choice options to formulate independent vector searches for each."})
        choice_k = max(2, top_k // 2)
        for choice in mcq_choices:
            safe_choice = _sanitize_lucene_query(choice.strip())
            res_choice = self._original_search(query_text=safe_choice, top_k=choice_k, **kwargs)
            if res_choice and res_choice.items:
                all_items.extend(res_choice.items)
                raw_local_count += len(res_choice.items)
                
    if status_callback:
        status_callback({"type": "step", "step": 3})
        status_callback({"type": "thought", "step": 3, "message": f"My local vector search identified {raw_local_count} raw document chunks matching the query."})

    # 3. Deduplicate and clean
    seen_content = set()
    unique_items = []
    for item in all_items:
        if item.content:
            item.content = item.content.replace('\n', ' ').replace('  ', ' ')
        sig = item.content.strip() if item.content else ""
        if sig and sig not in seen_content:
            seen_content.add(sig)
            unique_items.append(item)
            
    unique_items.sort(key=lambda x: x.metadata.get('score', 0.0) if x.metadata else 0.0, reverse=True)
    
    if status_callback:
        status_callback({"type": "step", "step": 3})
        status_callback({"type": "thought", "step": 3, "message": f"I optimized and deduplicated the results down to {len(unique_items)} unique highest-value entity chunks."})

    from neo4j_graphrag.retrievers.base import RetrieverResult
    return RetrieverResult(items=unique_items[:top_k * 2], metadata={})

def expand_query(self, query):
    """Bypass LLM query expansion.
    The pipeline now relies on independent vector searches for each MCQ choice
    to guarantee comprehensive coverage, rather than LLM-extracted keywords.
    """
    return query

def patched_vector_cypher_search(self, query_text, top_k=8, **kwargs):
    from neo4j_graphrag.retrievers.base import RetrieverResult
    original_query = kwargs.pop("original_query", query_text)
    use_global_kg = kwargs.pop("use_global_kg", False)
    status_callback = kwargs.pop("status_callback", None)
    
    # 1. KBPedia Search (via Neo4j)
    kb_items = []
    if use_global_kg and hasattr(self, 'llm') and self.llm:
        if not hasattr(self, 'kbpedia_retriever'):
             from .kbpedia_retriever import KBPediaRetriever
             self.kbpedia_retriever = KBPediaRetriever(driver=self._driver, llm=self.llm, top_k=top_k)
        
        kb_result = self.kbpedia_retriever.search(query_text, top_k=top_k, original_query=original_query, status_callback=status_callback)
        if kb_result and kb_result.items:
            kb_items = kb_result.items
            if status_callback:
                status_callback({"type": "step", "step": 3})
                status_callback({"type": "thought", "step": 3, "message": f"I searched the Global Knowledge Graph (KBPedia) and found {len(kb_items)} foundational facts."})

    # 2. Local Vector Search
    local_items = []
    MIN_SCORE = 0.4
    MIN_CONTENT_LENGTH = 5
    try:
        raw_local_items = []
        
        # Search main query
        res_main = self._original_search(query_text=query_text, top_k=top_k, **kwargs)
        if res_main and res_main.items:
            raw_local_items.extend(res_main.items)
            
        # Search MCQ choices
        mcq_choices = re.findall(r'\b[A-D][.)]\s*(.+)', original_query)
        if mcq_choices:
            print(f"DEBUG PROLOG-GRAPHRAG:[LocalDocs CypherVector] Extracted {len(mcq_choices)} MCQ choices for independent search.", flush=True)
            if status_callback:
                status_callback({"type": "step", "step": 3})
                status_callback({"type": "thought", "step": 3, "message": f"I extracted {len(mcq_choices)} multiple-choice options to run individual localized searches."})
            choice_k = max(2, top_k // 2)
            for choice in mcq_choices:
                res_choice = self._original_search(query_text=choice.strip(), top_k=choice_k, **kwargs)
                if res_choice and res_choice.items:
                    raw_local_items.extend(res_choice.items)

        # Filtering/Cleaning raw items
        filtered_items = []
        for item in raw_local_items:
            # Cleaning
            if item.metadata and 'local_context' in item.metadata:
                local_ctx = item.metadata['local_context']
                if local_ctx and isinstance(local_ctx, list) and len(local_ctx) > 0:
                    clean_text = local_ctx[0].get('text')
                    if clean_text:
                        item.content = clean_text
            elif item.content and "<Record" in str(item.content):
                match = re.search(r"text='(.*?)'", str(item.content))
                if match:
                    item.content = match.group(1)

            score = item.metadata.get('score', 0.0) if item.metadata else 0.0
            content = (item.content or "").strip()
            if score >= MIN_SCORE and len(content) >= MIN_CONTENT_LENGTH:
                filtered_items.append(item)
        local_items = filtered_items
        if status_callback:
            status_callback({"type": "step", "step": 3})
            status_callback({"type": "thought", "step": 3, "message": f"My local Cypher vector search identified {len(raw_local_items)} raw chunks; I filtered this down to {len(local_items)} highly relevant nodes."})
    except Exception as e:
        print(f"DEBUG PROLOG-GRAPHRAG:Main retriever failed: {e}")
        
    all_items = kb_items + local_items
    for item in all_items:
        if 'score' not in item.metadata:
            item.metadata['score'] = 0.0
    all_items.sort(key=lambda x: x.metadata.get('score', 0.0), reverse=True)
    
    # Deduplication
    seen_content = set()
    unique_items = []
    for item in all_items:
        if item.content:
            item.content = item.content.replace('\n', ' ').replace('  ', ' ')
        sig = item.content.strip() if item.content else ""
        if sig not in seen_content:
            seen_content.add(sig)
            unique_items.append(item)
            
    if status_callback:
        status_callback({"type": "step", "step": 3})
        status_callback({"type": "thought", "step": 3, "message": f"I deduplicated and ranked the results down to {len(unique_items)} highest-signal semantic chunks."})
    
    final_top_k = top_k * 2 if (kb_items and local_items) else top_k
    return RetrieverResult(items=unique_items[:final_top_k], metadata={})


# YAGO index creation removed — YAGO is no longer used as a knowledge source.

def create_retriever(driver, embedder):
    if not check_db_health(driver):
        raise ConnectionError("Aborting initialization: Cannot connect to Neo4j.")
    
    # 2. Cleanup Phase (Only for local document indexes)
    driver.execute_query("DROP INDEX documentsVectorIndex IF EXISTS")
    driver.execute_query("DROP INDEX documentsFulltextIndex IF EXISTS")
    
    # 3. (YAGO index removed — no longer needed)

    # 4. Recreate Phase
    create_indexes(driver)
    
    # 5. Guarded Wait Phase
    try:
        wait_for_indexes(driver, timeout=30) 
    except TimeoutError as e:
        print(f"Critical Error: {e}")
        return None

    # 6. Initialization
    if RETRIEVER == "HybridRetriever":
        r = HybridRetriever(
            driver=driver,
            vector_index_name="documentsVectorIndex",
            fulltext_index_name="documentsFulltextIndex",
            embedder=embedder,
            
        )
        # Monkey-patch
        r._original_search = r.search
        r.search = types.MethodType(patched_hybrid_search, r)
        return r
    else:
        raise ValueError(f"Retriever {RETRIEVER} is invalid.")
    
    # Monkey-patch driver if not present
    # This section is removed as it's no longer needed with the new patching approach.


def generate(llm, retriever, query, original_query: str = "", fallback: str = "prolog-graphrag") -> dict:
    # If the retriever is our EnhancedRetriever, inject the LLM
    if hasattr(retriever, 'llm'):
        retriever.llm = llm

    retriever_config = {'top_k': 12}
    if original_query:
        retriever_config['original_query'] = original_query

    # Run retrieval
    retrieved_result = retriever.search(query, **retriever_config)
    retrieved_context = retrieved_result

    # Build context string for the LLM
    context_str = ""
    if retrieved_context and hasattr(retrieved_context, 'items'):
        context_str = "\n".join([item.content for item in retrieved_context.items])
        
    # Call LLM directly with System/User messages to prevent fact hallucination/repetition
    from ..llm_config import get_openai_client, MODEL_NAME
    try:
        from .config import GRAPHRAG_SYSTEM_PROMPT, GRAPHRAG_FALLBACK_SYSTEM_PROMPT
    except ImportError:
        from config import GRAPHRAG_SYSTEM_PROMPT, GRAPHRAG_FALLBACK_SYSTEM_PROMPT

    client = get_openai_client()
    
    messages = [
        {"role": "system", "content": GRAPHRAG_SYSTEM_PROMPT if not fallback else GRAPHRAG_FALLBACK_SYSTEM_PROMPT},
        {"role": "user", "content": "Acknowledge these strict instructions. You must extract unbiased facts and aggressively deduplicate any repeating concepts."},
        {"role": "assistant", "content": "I understand and will follow all instructions strictly. I will extract unbiased, reasoning-ready facts, end them with parenthetical tags like (Global) or (Choice A), and absolutely will not repeat the same fact in different words. Please provide the Question and Context."},
        {"role": "user", "content": f"### QUESTION:\n{original_query if original_query else query}\n\n### CONTEXT:\n{context_str}"}
    ]
    
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.3,
            logprobs=True
        )
        answer = response.choices[0].message.content
    except Exception as e:
        print(f"Error calling LLM for Logical Evidence: {e}")
        answer = "No logical evidence available."

    # Enrich context with metadata for the LLM
    final_contexts = []
    
    output_file = "debug_rag_output.txt"
    
    with open(output_file, "a", encoding="utf-8") as f:
        f.write("="*50 + "\n")
        f.write(f" QUERY: {query}\n")
        f.write("="*50 + "\n\n")
        f.write(f"--- RETRIEVED CONTEXT (Top {len(retrieved_context.items)} Items) ---\n")
        
        for i, item in enumerate(retrieved_context.items):
            # Fix Score: config.py now puts 'score' in metadata
            metadata = item.metadata or {}
            score = metadata.get('score', 0.0) 

            # Add Metadata Dump (requested by user)
            f.write(f"\n[Metadata Dump]\n{json.dumps(metadata, indent=2)}\n") 
            
            # Fix Content: Unwrap if it is a Neo4j Record string representation or just use metadata text
            # If item.content looks like "<Record ...>", we try to clean it.
            clean_content = item.content
            if clean_content and "<Record" in str(clean_content):
                # Try to extract text='...'
                match = re.search(r"text='(.*?)'", str(clean_content))
                if match:
                    clean_content = match.group(1)
                else:
                    # Fallback: Check if local_context is present and has text
                    local_ctx = metadata.get('local_context', [])
                    if local_ctx and len(local_ctx) > 0:
                         clean_content = local_ctx[0].get('text', clean_content)
                    
            # Only collapse newlines for raw Neo4j Record strings or plain text chunks.
            # KBPedia content already has intentional \n-separated fact bullets — preserve them.
            is_kbpedia_src = metadata.get('source') == 'KBPedia'
            if not is_kbpedia_src:
                clean_content = clean_content.replace('\n', ' ').replace('  ', ' ')
            
            # Extract Local/Global Context
            local_ctx = metadata.get('local_context', [])
            global_ctx = metadata.get('global_context', [])
            
            enriched_content = f"[Chunk Score: {score:.4f}] {clean_content}\n"
            
            if local_ctx:
                enriched_content += "  [Local Connections]:\n"
                for lc in local_ctx:
                    enriched_content += f"   - {lc.get('entity')} {lc.get('relationship')} {lc.get('target')}\n"
            
    
            # KBPedia items already embed triples inside clean_content ("Relevant Logical Facts"),
            # so skip to avoid duplicating them.
            kg_triples = metadata.get('triples', [])
            is_kbpedia = metadata.get('source') == 'KBPedia'
            if kg_triples and not is_kbpedia:
                 enriched_content += "  [Knowledge Graph Triples]:\n"
                 for t in kg_triples:
                     enriched_content += f"   - {t}\n"

            if global_ctx:
                enriched_content += "  [Global Knowledge]:\n"
                for gc in global_ctx:
                     enriched_content += f"   - {gc.get('concept')}: {gc.get('definition')} (Score: {gc.get('score'):.2f})\n"

            final_contexts.append(enriched_content)

            f.write(f"[Item {i+1}]\n")
            f.write(f"{enriched_content}\n")
            f.write("-" * 50 + "\n")

        f.write("\n" + "="*50 + "\n")
        f.write(" LLM ANSWER:\n")
        f.write("="*50 + "\n")
        f.write(f"{answer}\n")
        f.write("="*50 + "\n")

    print(f"Done. Check '{output_file}' for the context and answer.")

    return {
        "answer": answer,
        "contexts": final_contexts
    }