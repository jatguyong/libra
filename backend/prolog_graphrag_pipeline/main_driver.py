"""Pipeline orchestrator — the central entry point for answering a question.

``run_pipeline()`` coordinates the full flow:

  1. **Routing** — decides whether the question needs the full
     Prolog-GraphRAG path or can be answered directly by the LLM.
  2. **GraphRAG retrieval** — searches the Neo4j knowledge graph
     (user-uploaded documents + KBPedia global concepts).
  3. **Prolog reasoning** — generates s(CASP) Prolog code, validates it,
     runs the solver, and produces a natural-language explanation.
  4. **LLM synthesis** — merges retrieved context and Prolog output into
     a final answer, with semantic-entropy hallucination checks.

Progress is reported via ``status_callback`` so the frontend can
display real-time pipeline step indicators.
"""
import logging
import time
import re
from typing import Literal


from .graphrag import graphrag_driver
from .prolog import prolog_driver
from .llm import generate, decide_fallback
from .prompt_reconstructor import reconstruct_prompt
from .semantic_entropy import compute_semantic_entropy
from .config import COMPUTE_SEMANTIC_ENTROPY  # kept for potential future use


logger = logging.getLogger(__name__)


def _clean_text(text_val) -> str:
    """Normalize a retriever item's content field to a plain string."""
    if not text_val:
        return ""
    if isinstance(text_val, dict):
        return text_val.get("text", text_val.get("content", str(text_val)))
    stripped = str(text_val).strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            import json as _json
            import ast as _ast
            d = None
            try:
                d = _json.loads(stripped)
            except Exception:
                try:
                    d = _ast.literal_eval(stripped)
                except Exception:
                    pass
            if isinstance(d, dict):
                return d.get("text", d.get("content", text_val))
        except Exception:
            pass
    return str(text_val)


def run_pipeline(
    question: str,
    flag: Literal['q', r"x\c", "x"],
    sample_mode: bool = True,
    use_global_kg: bool = False,
    force_prolog: bool = False,
    calculate_semantic_entropy: bool = False,
    status_callback=None,
) -> dict:
    start_time = time.perf_counter()

    if status_callback:
        status_callback({"type": "step", "step": 1})

    # Router decides which pipeline path to take
    if force_prolog:
        fallback = "prolog-graphrag"
        if status_callback:
            status_callback({"type": "thought", "step": 1, "message": "The user explicitly enabled the Prolog-GraphRAG path, so I'll route this question directly there without evaluating its complexity."})
    else:
        fallback = decide_fallback(question)
        if status_callback:
            if fallback == "prolog-graphrag":
                msg = "This question requires deep logical reasoning and external knowledge, so it's best suited for the full Prolog-GraphRAG pipeline."
            elif fallback == "graphrag":
                msg = "This question involves extracting factual context, so I'll route it through the standard GraphRAG retriever."
            else:
                msg = "This question is straightforward enough for me to answer directly from my own memory."
            status_callback({"type": "thought", "step": 1, "message": msg})
            
    logger.info(f"Question: {question}")

    if fallback == "tuned":
        if status_callback:
            status_callback({"type": "step", "step": 2, "fallback": fallback})
            status_callback({"type": "thought", "step": 2, "message": "I bypassed the knowledge graph and routed your question directly to my internal parametric memory for a quick conversational response."})
        # Tuned LLM never uses sample_mode — no semantic entropy for simple responses
        llm_output = generate(
            question, retrieved_context=None, explainer_output=None,
            fallback=fallback, flag=flag, sample_mode=False, status_callback=status_callback,
        )
        if isinstance(llm_output, dict):
            final_answer = llm_output.get("text_answer", "Error generating answer")
            logprobs = llm_output.get("logprobs", [])
        else:
            final_answer = "Error generating answer"
            logprobs = []

        return {
            "answer": final_answer,
            "logprobs": logprobs,
            "database": None,
            "query": None,
            "contexts": None,
            "prolog_explanation": None,
            "explainer_output": None,
            "prolog_error": None,
            "fallback": fallback,
        }

    # Non-tuned path: run GraphRAG retrieval first
    graphrag_output = (
        graphrag_driver.run_pipeline(
            question=question, fallback=fallback,
            use_global_kg=use_global_kg, status_callback=status_callback,
        )
        if flag != "q" else None
    )
    graphrag_answer = graphrag_output.get("answer", "") if graphrag_output else ""
    graphrag_logprobs = graphrag_output.get("logprobs", []) if graphrag_output else []
    graphrag_retriever_result = graphrag_output.get("retriever_results", []) if graphrag_output else []
    # DEBUG: log the exact type and attributes of retriever_result
    logger.info(f"[GraphDebug] retriever_result type: {type(graphrag_retriever_result)}, dir: {[a for a in dir(graphrag_retriever_result) if not a.startswith('_')]}")
    if hasattr(graphrag_retriever_result, 'items'):
        _items_val = graphrag_retriever_result.items
        logger.info(f"[GraphDebug] .items type: {type(_items_val)}, len: {len(_items_val) if hasattr(_items_val, '__len__') else 'N/A'}")
        if callable(_items_val):
            graphrag_retriever_results = list(_items_val())
        else:
            graphrag_retriever_results = list(_items_val) if _items_val else []
    else:
        graphrag_retriever_results = graphrag_retriever_result if isinstance(graphrag_retriever_result, list) else []
    logger.info(f"[GraphDebug] graphrag_retriever_results count: {len(graphrag_retriever_results)}")
    if graphrag_retriever_results:
        first = graphrag_retriever_results[0]
        logger.info(f"[GraphDebug] First item type: {type(first)}, metadata keys: {list(getattr(first, 'metadata', {}).keys()) if hasattr(first, 'metadata') else 'N/A'}")
    query = graphrag_output.get("query", question) if graphrag_output else question

    # Build context strings from retriever results
    condensed_context = ""
    raw_context_strings = []

    if flag != "q" and graphrag_output and fallback != "tuned":
        logger.debug("GRAPHRAG CONDENSED CONTEXT:\n%s", graphrag_output.get("answer", "No condensed context found."))
        condensed_context = graphrag_answer

        # Classify retriever results by source (KBPedia vs Wikidata)
        for item in graphrag_retriever_results:
            src = ""
            if hasattr(item, "metadata"):
                src = (item.metadata or {}).get("source", "")
            elif isinstance(item, dict):
                src = item.get("metadata", {}).get("source", "")
            
            # Use item.content heavily like retriever.generate() does
            content = ""
            if hasattr(item, "content"):
                content = item.content
            elif isinstance(item, dict):
                content = item.get("content", "")
            
            raw_context_strings.append(content)

    retrieved_context_str = condensed_context if graphrag_output else ""
    
    # Extract Nodes and Edges for Visual Graph
    graph_nodes = {}
    graph_edges = []
    
    if flag != "q" and graphrag_output and fallback != "tuned":
        # --- Source 1: KBPedia / retriever metadata triples & Chunks ---
        for idx, item in enumerate(graphrag_retriever_results):
            metadata = {}
            if hasattr(item, "metadata"):
                metadata = item.metadata or {}
            elif isinstance(item, dict):
                metadata = item.get("metadata", {})
            
            source_label = metadata.get("source", "unknown")
            source_entity = metadata.get("entity", "")
            
            # Extract chunk content and create a Chunk node
            chunk_content = ""
            if hasattr(item, "content"):
                chunk_content = item.content
            elif isinstance(item, dict):
                chunk_content = item.get("content", "")
            
            # Use elementId if available from RetrieverResultItem metadata
            chunk_id = str(metadata.get('id', ""))
            if not chunk_id and chunk_content:
                # Fallback to hash only if elementId is totally missing
                chunk_id = str(hash(str(chunk_content)[:100]))
            
            doc_id = str(source_label)  # Document name
            
            chunk_content = _clean_text(chunk_content)
            
            if chunk_content:
                # Always Create Chunk Node - Increase display limit to 500
                display_chunk = chunk_content[:500] + "..." if len(chunk_content) > 500 else chunk_content
                # Differentiate chunk types by source
                chunk_label = "KBPediaChunk" if source_label == "KBPedia" else "DocumentChunk"
                graph_nodes[chunk_id] = {"id": chunk_id, "name": display_chunk, "label": chunk_label, "val": 15}
                
                # Link Chunk to Document if it is a real file (not a system KB)
                if doc_id and doc_id not in ["unknown", "KBPedia", "Wikidata"]:
                    graph_nodes[doc_id] = {"id": doc_id, "label": "Document"}
                    graph_edges.append({"source": chunk_id, "target": doc_id, "label": "FROM_DOCUMENT"})
            
            # Process local_context (from VectorCypher retriever)
            local_ctx = metadata.get("local_context", [])
            for lc in local_ctx:
                if isinstance(lc, dict):
                    source = lc.get("entity")
                    target = lc.get("target")
                    rel = lc.get("relationship")
                    if source and target and rel:
                        graph_nodes[str(source)] = {"id": str(source), "label": "Entity"}
                        graph_nodes[str(target)] = {"id": str(target), "label": "Entity"}
                        graph_edges.append({"source": str(source), "target": str(target), "label": str(rel)})
                        
                        # Link this chunk to the entities it extracted/mentions
                        if chunk_id:
                            graph_edges.append({"source": chunk_id, "target": str(source), "label": "FROM_CHUNK"})
                            graph_edges.append({"source": chunk_id, "target": str(target), "label": "FROM_CHUNK"})
                        
            # Process KBPedia / Knowledge Graph Triples
            kg_triples = metadata.get("triples", [])
            node_label = "KBPediaConcept"  # default, may be overridden per triple
            
            # Always register the concept entity as a node, even if no edges can be built
            if source_entity and kg_triples:
                graph_nodes[str(source_entity)] = {"id": str(source_entity), "label": node_label}
                # Link Chunk to the master Entity concept it grounds to
                if chunk_id:
                    graph_edges.append({"source": chunk_id, "target": str(source_entity), "label": "GROUNDS_TO"})
            
            for t in kg_triples:
                if isinstance(t, str):
                    # Handle (Wikidata) prefix
                    clean_t = t
                    triple_source = "KG"
                    if t.startswith("("):
                        paren_match = re.match(r'\(([^)]*)\)\s*(.*)', t)
                        if paren_match:
                            triple_source = paren_match.group(1)
                            clean_t = paren_match.group(2).strip()
                    
                    # Format: "relationship: target" e.g. "definition: ...", "subclass of: ..."
                    node_label = "WikidataConcept" if triple_source == "Wikidata" else "KBPediaConcept"
                    if ":" in clean_t and source_entity:
                        rel, target = clean_t.split(":", 1)
                        rel, target = rel.strip(), target.strip()
                        if target:
                            display_target = target[:400] + "…" if len(target) > 400 else target
                            # Ensure both nodes exist
                            if str(source_entity) not in graph_nodes:
                                graph_nodes[str(source_entity)] = {"id": str(source_entity), "label": "KBPediaConcept"}
                            graph_nodes[str(display_target)] = {"id": str(display_target), "label": node_label}
                            graph_edges.append({"source": str(source_entity), "target": str(display_target), "label": rel})
                    else:
                        # Try known relationship keywords: "Source RELATIONSHIP Target"
                        parts = []
                        for rel_key in [" SUBCLASS_OF ", " PART_OF ", " RELATED_TO ", " CAUSES ", " PRODUCES ", " REQUIRES ", " OCCURS_IN ", " DISCOVERED_BY ", " DEFINES ", " IS_A "]:
                            if rel_key in clean_t:
                                s, tgt = clean_t.split(rel_key, 1)
                                parts = [s.strip(), rel_key.strip(), tgt.strip()]
                                break
                        
                        if not parts:
                            temp_parts = clean_t.split(" ", 2)
                            if len(temp_parts) >= 3:
                                parts = [temp_parts[0], temp_parts[1], temp_parts[2]]
                        
                        if len(parts) >= 3:
                            source, rel, target = parts[0], parts[1], parts[2]
                            graph_nodes[str(source)] = {"id": str(source), "label": node_label}
                            graph_nodes[str(target)] = {"id": str(target), "label": node_label}
                            graph_edges.append({"source": str(source), "target": str(target), "label": str(rel)})

        # Mark Source 1 (Retriever Results) as being part of the filtered view
        for node in graph_nodes.values():
            node["in_filtered_view"] = True
        for edge in graph_edges:
            edge["in_filtered_view"] = True

        # --- Source 2: Global Neo4j Discovery (Fetch ALL relationships for retrieved DocumentChunks) ---
        # Only query Neo4j for real document chunks (not KBPedia virtual chunks)
        chunk_ids_to_query = [str(n["id"]) for n in graph_nodes.values() if n.get("label") == "DocumentChunk"]
        logger.info(f"[GraphData] DocumentChunk IDs for Neo4j discovery: {len(chunk_ids_to_query)} IDs: {chunk_ids_to_query[:5]}")
        
        if chunk_ids_to_query:
            try:
                from .graphrag.neo4j_manager import get_driver
                neo4j_driver = get_driver()
                
                # Simplified but robust discovery:
                # 1. Fetch ALL relationships for our retrieved chunks (1-hop)
                # 2. Specifically fetch the NEXT_CHUNK / FROM_DOCUMENT chain for the related documents.
                records2, _, _ = neo4j_driver.execute_query(
                    """
                    MATCH (s)-[r]->(t)
                    WHERE elementId(s) IN $chunk_ids OR elementId(t) IN $chunk_ids
                    RETURN 
                        elementId(s) AS s_id, labels(s) AS s_labels, properties(s) AS s_props,
                        type(r) AS rel_label,
                        elementId(t) AS t_id, labels(t) AS t_labels, properties(t) AS t_props
                    UNION
                    MATCH (d:Document)<-[:FROM_DOCUMENT]-(c:Chunk)
                    WHERE elementId(c) IN $chunk_ids
                    MATCH (s:Chunk)-[r:NEXT_CHUNK|FROM_DOCUMENT]->(t)
                    WHERE (s)-[:FROM_DOCUMENT]->(d)
                    RETURN 
                        elementId(s) AS s_id, labels(s) AS s_labels, properties(s) AS s_props,
                        type(r) AS rel_label,
                        elementId(t) AS t_id, labels(t) AS t_labels, properties(t) AS t_props
                    """,
                    chunk_ids=chunk_ids_to_query,
                    database_="neo4j"
                )
                
                for rec in records2:
                    s_id = str(rec["s_id"] or "")
                    t_id = str(rec["t_id"] or "")
                    if not s_id or not t_id: continue

                    # Process Nodes
                    for n_prefix in ["s", "t"]:
                        n_id = s_id if n_prefix == "s" else t_id
                        n_labels = rec[f"{n_prefix}_labels"]
                        n_props = rec[f"{n_prefix}_props"] or {}
                        
                        if n_id not in graph_nodes:
                            n_label = n_labels[0] if n_labels else "Entity"
                            
                            # Clean/Short Name for Label
                            raw_text = n_props.get("text", n_props.get("name", n_props.get("path", n_id)))
                            def clean_val(v):
                                if not v: return ""
                                v_str = str(v).strip()
                                if v_str.startswith("{") and v_str.endswith("}"):
                                    try:
                                        import json, ast
                                        d = None
                                        try: d = json.loads(v_str)
                                        except:
                                            try: d = ast.literal_eval(v_str)
                                            except: pass
                                        if isinstance(d, dict): return d.get("text", d.get("content", v_str))
                                    except: pass
                                return v_str

                            full_text = clean_val(raw_text)
                            display_name = full_text[:80] + "..." if len(full_text) > 80 else full_text
                            if n_label == "Document":
                                display_name = n_props.get("path", "Document").split("/")[-1]
                            elif n_label == "Chunk":
                                n_label = "DocumentChunk"  # Reclassify Neo4j Chunk as DocumentChunk
                                display_name = f"Chunk {n_props.get('index', '?')}: {full_text[:40]}..."

                            graph_nodes[n_id] = {
                                "id": n_id, 
                                "name": display_name, 
                                "label": n_label,
                                "properties": n_props,  # Send full properties to frontend
                                "in_filtered_view": False
                            }
                    
                    # Add edge
                    graph_edges.append({"source": s_id, "target": t_id, "label": str(rec["rel_label"]), "in_filtered_view": False})
                        
            except Exception as e:
                logger.warning(f"[GraphData] Global discovery failed: {e}")

    # Deduplicate edges
    unique_edges = set()
    deduped_graph_edges = []
    for edge in graph_edges:
        sig = (str(edge.get("source")), str(edge.get("target")), str(edge.get("label")))
        if sig not in unique_edges:
            unique_edges.add(sig)
            deduped_graph_edges.append(edge)

    graph_data = {
        "nodes": list(graph_nodes.values()),
        "edges": deduped_graph_edges
    }
    
    logger.info(f"Extracted graph_data: {len(graph_data['nodes'])} nodes, {len(graph_data['edges'])} edges")

    # Prolog-GraphRAG path
    pgr_results = {}
    prolog_error, explainer_output, final_answer = None, None, None
    llm_logprobs = []

    if fallback == "prolog-graphrag":
        try:
            pgr_results = (
                prolog_driver.run_pipeline(
                    question=question, retrieved_context=condensed_context,
                    status_callback=status_callback,
                )
                if flag != "q" else None
            )
        except Exception as e:
            prolog_error = f"Error occurred while running Prolog pipeline: {e}"
        else:
            explainer_output = pgr_results.get("explainer_output", "") if pgr_results else ""
            if status_callback:
                status_callback({"type": "step", "step": 9})
            llm_output = (
                generate(
                    question, retrieved_context_str, explainer_output,
                    flag=flag, sample_mode=(sample_mode and calculate_semantic_entropy),
                    fallback=fallback, status_callback=status_callback,
                )
                if prolog_error is None
                else pgr_results.get("final_answer", "")
            )
            if isinstance(llm_output, list) and len(llm_output) > 0:
                final_answer = llm_output[0].get("text_answer", "Error generating answer")
                llm_logprobs = llm_output[0].get("logprobs", [])
            elif isinstance(llm_output, dict):
                final_answer = llm_output.get("text_answer", "Error generating answer")
                llm_logprobs = llm_output.get("logprobs", [])
            else:
                final_answer = str(llm_output) if llm_output else "Error generating answer"
                llm_logprobs = []
    else:
        # GraphRAG-only fallback (Prolog skipped)
        prolog_error = "Pipeline decided to fallback to GraphRAG, skipping Prolog execution."
        explainer_output = "No explainer output since Prolog was skipped."
        final_answer = graphrag_output.get("answer", "Error generating answer") if graphrag_output else "Error generating answer"
        llm_output = None

    logprobs = llm_logprobs if fallback == "prolog-graphrag" else graphrag_logprobs

    if prolog_error:
        logger.warning("Prolog error: %s", prolog_error)
    else:
        logger.info("Prolog executed successfully.")

    duration = time.perf_counter() - start_time
    logger.info("Pipeline finished in %.4fs. Prolog verified: %s", duration, prolog_error is None)

    # Helper to safely pull from pgr_results (may be None or {})
    def _pgr(key: str, default=""):
        return pgr_results.get(key, default) if pgr_results else default

    if not sample_mode:
        return {
            "answer": final_answer or "Error generating answer",
            "database": _pgr("database", "No database generated."),
            "prolog_query": _pgr("query", "No prolog query generated."),
            "query": query,
            "condensed_context": condensed_context,
            "contexts": raw_context_strings if raw_context_strings else retrieved_context_str,
            "prolog_explanation": _pgr("prolog_explanation"),
            "explainer_output": _pgr("explainer_output", "No explainer output generated."),
            "prolog_error": _pgr("prolog_error") or None,
            "fallback": fallback,
            "graph_data": graph_data,
        }

    # sample_mode path — but SE is disabled OR llm_output came back as a single
    # dict (because generate() was called with sample_mode=False due to the
    # COMPUTE_SEMANTIC_ENTROPY guard). Either way, final_answer is already set.
    if not isinstance(llm_output, list) or len(llm_output) == 0:
        return {
            "answer": final_answer or "Error generating answer",
            "database": _pgr("database", "No database generated."),
            "prolog_query": _pgr("query", "No prolog query generated."),
            "query": query,
            "condensed_context": condensed_context,
            "contexts": raw_context_strings if raw_context_strings else retrieved_context_str,
            "prolog_explanation": _pgr("prolog_explanation"),
            "explainer_output": _pgr("explainer_output", "No explainer output generated."),
            "prolog_error": _pgr("prolog_error") or prolog_error,
            "fallback": fallback,
            "graph_data": graph_data,
        }

    # llm_output is a proper list of samples — safe to unpack
    answers = [output["text_answer"] for output in llm_output]
    logprobs = [output["logprobs"] for output in llm_output]

    if not calculate_semantic_entropy:
        # Flag disabled at runtime — skip entropy scoring, return first sample
        return {
            "answer": answers[0] if answers else "Error generating answer",
            "database": _pgr("database", "No database generated."),
            "prolog_query": _pgr("query", "No prolog query generated."),
            "query": query,
            "condensed_context": condensed_context,
            "contexts": raw_context_strings if raw_context_strings else retrieved_context_str,
            "prolog_explanation": _pgr("prolog_explanation"),
            "explainer_output": _pgr("explainer_output", "No explainer output generated."),
            "prolog_error": _pgr("prolog_error") or None,
            "fallback": fallback,
            "graph_data": graph_data,
        }

    se_results = compute_semantic_entropy({"sequences": answers, "logprobs": logprobs})

    return {
        "answers": answers,
        "logprobs": logprobs,
        "best_answer": se_results["best_answer"],
        "semantic_entropy": se_results["semantic_entropy"],
        "hallucination_flag": se_results["hallucination_flag"],
        "database": _pgr("database", "No database generated."),
        "prolog_query": _pgr("query", "No prolog query generated."),
        "query": query,
        "condensed_context": condensed_context,
        "contexts": raw_context_strings if raw_context_strings else retrieved_context_str,
        "prolog_explanation": _pgr("prolog_explanation"),
        "explainer_output": _pgr("explainer_output", "No explainer output generated."),
        "prolog_error": _pgr("prolog_error") or None,
        "fallback": fallback,
        "graph_data": graph_data,
    }


if __name__ == "__main__":
    prompt = "Which of the following parts of a plant cell has a function that is most similar to the function of an animal skeleton?"
    logger.info("Running pipeline with prompt: '%s'", prompt)
    output = run_pipeline(prompt, flag="x")
    logger.info("Final Answer: %s", output.get("answer"))