import logging
import time
from typing import Literal

from .graphrag import graphrag_driver
from .prolog import prolog_driver
from .llm import generate, decide_fallback
from .prompt_reconstructor import reconstruct_prompt
from .semantic_entropy import compute_semantic_entropy
import re

logger = logging.getLogger(__name__)


def run_pipeline(
    question: str,
    flag: Literal['q', r"x\c", "x"],
    sample_mode: bool = True,
    use_global_kg: bool = False,
    force_prolog: bool = False,
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
    # RetrieverResult is a Pydantic model with .items; unwrap to the actual list
    if hasattr(graphrag_retriever_result, 'items'):
        graphrag_retriever_results = graphrag_retriever_result.items
    else:
        graphrag_retriever_results = graphrag_retriever_result if isinstance(graphrag_retriever_result, list) else []
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
        # --- Source 1: KBPedia / retriever metadata triples ---
        for idx, item in enumerate(graphrag_retriever_results):
            metadata = {}
            if hasattr(item, "metadata"):
                metadata = item.metadata or {}
            elif isinstance(item, dict):
                metadata = item.get("metadata", {})
            
            source_label = metadata.get("source", "unknown")
            source_entity = metadata.get("entity", "")
            
            logger.debug(f"[GraphData] Item {idx}: source={source_label}, entity={source_entity}, "
                         f"has_triples={bool(metadata.get('triples'))}, "
                         f"has_local_context={bool(metadata.get('local_context'))}, "
                         f"metadata_keys={list(metadata.keys())}")
                
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
                        
            # Process KBPedia / Knowledge Graph Triples
            kg_triples = metadata.get("triples", [])
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
                        if target and len(target) < 200:  # Skip very long definition text
                            graph_nodes[str(source_entity)] = {"id": str(source_entity), "label": node_label}
                            graph_nodes[str(target)] = {"id": str(target), "label": node_label}
                            graph_edges.append({"source": str(source_entity), "target": str(target), "label": rel})
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

        # --- Source 2: Fetch local document graph relationships directly from Neo4j ---
        try:
            from .graphrag.neo4j_manager import get_driver
            neo4j_driver = get_driver()
            
            # Query 1: Entity-to-Entity relationships (created by SimpleKGPipeline)
            records, _, _ = neo4j_driver.execute_query(
                """
                MATCH (a)-[r]->(b)
                WHERE NOT a:Chunk AND NOT b:Chunk
                  AND NOT a:Document AND NOT b:Document
                  AND NOT a:KBPediaConcept AND NOT b:KBPediaConcept
                  AND NOT type(r) IN ['EMBEDDING', 'FROM_DOCUMENT', 'NEXT_CHUNK', 'HAS_DOCUMENT']
                RETURN DISTINCT
                    coalesce(a.name, a.id, toString(id(a))) AS source_name,
                    labels(a)[0] AS source_label,
                    type(r) AS relationship,
                    coalesce(b.name, b.id, toString(id(b))) AS target_name,
                    labels(b)[0] AS target_label
                LIMIT 150
                """,
                database_="neo4j"
            )
            for rec in records:
                src = str(rec["source_name"])
                tgt = str(rec["target_name"])
                rel = str(rec["relationship"])
                s_label = rec.get("source_label", "Entity")
                t_label = rec.get("target_label", "Entity")
                if src and tgt and rel:
                    graph_nodes[src] = {"id": src, "label": s_label or "Entity"}
                    graph_nodes[tgt] = {"id": tgt, "label": t_label or "Entity"}
                    graph_edges.append({"source": src, "target": tgt, "label": rel})
            logger.info(f"[GraphData] Neo4j entity graph query returned {len(records)} relationships.")
            
            # Query 2: Chunk-to-Entity relationships (knowledge extraction links)
            records2, _, _ = neo4j_driver.execute_query(
                """
                MATCH (c:Chunk)-[r]->(e)
                WHERE NOT type(r) IN ['EMBEDDING', 'FROM_DOCUMENT', 'NEXT_CHUNK', 'PART_OF_CHUNK']
                  AND NOT e:Chunk AND NOT e:Document
                RETURN DISTINCT
                    coalesce(c.text, c.id, toString(id(c))) AS source_name,
                    type(r) AS relationship,
                    coalesce(e.name, e.id, e.text, toString(id(e))) AS target_name,
                    labels(e)[0] AS target_label
                LIMIT 100
                """,
                database_="neo4j"
            )
            for rec in records2:
                src = str(rec["source_name"])[:80]   # Truncate long chunk text
                tgt = str(rec["target_name"])
                rel = str(rec["relationship"])
                t_label = rec.get("target_label", "Entity")
                if src and tgt and rel:
                    graph_nodes[src] = {"id": src, "label": "Chunk"}
                    graph_nodes[tgt] = {"id": tgt, "label": t_label or "Entity"}
                    graph_edges.append({"source": src, "target": tgt, "label": rel})
            logger.info(f"[GraphData] Neo4j chunk-entity query returned {len(records2)} relationships.")
        except Exception as e:
            logger.warning(f"[GraphData] Failed to fetch local graph from Neo4j: {e}")

    graph_data = {
        "nodes": list(graph_nodes.values()),
        "edges": graph_edges
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
                    flag=flag, sample_mode=sample_mode, fallback=fallback,
                    status_callback=status_callback,
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

    # sample_mode: run semantic entropy if we have multiple LLM samples
    if not isinstance(llm_output, list) or len(llm_output) == 0:
        # No multi-sample output (e.g. graphrag-only path) — skip SE
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

    answers = [output["text_answer"] for output in llm_output]
    logprobs = [output["logprobs"] for output in llm_output]
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