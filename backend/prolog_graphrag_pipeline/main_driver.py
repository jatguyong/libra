from .graphrag import graphrag_driver
from .prolog import prolog_driver
from .llm import generate, decide_fallback
from .prompt_reconstructor import reconstruct_prompt
from .semantic_entropy import compute_semantic_entropy
from .graphrag.config import SKIP_LOGICAL_EVIDENCE_LLM
    
import time
from typing import Literal

def run_pipeline(question: str, flag: Literal['q', r"x\c", "x"], sample_mode: bool = False, use_global_kg: bool = False, status_callback=None) -> dict:
    start_time = time.perf_counter()
    
    if status_callback:
        status_callback({"type": "step", "step": 1})

    if flag != "q":
        pass
    
    # Separate inference run for deciding if pipeline would fall back to GraphRAG
    fallback = decide_fallback(question)
    print(f"    Question: {question}")
    # if fallback == "prolog-graphrag":
    #     # print("     Fallback decision: NO — proceeding with Prolog inference.\n")
    # elif fallback == "graphrag":
    #     # print("     Fallback decision: YES — skipping Prolog and using GraphRAG answer directly.\n")
    # elif fallback == "tuned":
    #     # print("     Fallback decision: YES — skipping Prolog and using LLM answer directly.\n")
    # else:
    #     raise ValueError(f"Invalid fallback {fallback}")
    # fallback = "prolog-graphrag"
    if fallback == "tuned":
        if status_callback:
            status_callback({"type": "step", "step": 2, "fallback": fallback})
        llm_output = generate(question, retrieved_context=None, explainer_output=None, fallback=fallback, flag=flag, sample_mode=sample_mode, status_callback=status_callback)
        final_answer = llm_output.get("text_answer", "Error generating answer") if llm_output else "Error generating answer"
        logprobs = llm_output.get("logprobs", "") if llm_output else ""
        
        # Return different dicts depending on sample_mode
        if not sample_mode:
            return {
                "answer": final_answer,
                "logprobs": logprobs,
                "database": None,
                "query": None,
                "contexts": None,
                "prolog_explanation": None,
                "explainer_output": None,
                "prolog_error": None,
                "fallback": fallback
            }
        else:
            return {
                "answers": [output["text_answer"] for output in llm_output],
                "logprobs": [output["logprobs"] for output in llm_output]
            }
    else:
        graphrag_output = graphrag_driver.run_pipeline(question=question, fallback=fallback, use_global_kg=use_global_kg, status_callback=status_callback) if flag != "q" else None
        graphrag_answer = graphrag_output.get("answer", "") if graphrag_output else ""
        graphrag_logprobs = graphrag_output.get("logprobs", []) if graphrag_output else {}
        graphrag_retriever_results = graphrag_output.get("retriever_results", []) if graphrag_output else []
        query = graphrag_output.get("query", question) if graphrag_output else question
        raw_context_strings = []
        condensed_context = ""
        
        if flag != "q" and graphrag_output and fallback != "tuned":
            # Print the intermediate GraphRAG logical evidence to the terminal for transparency
            print("\n" + "="*80)
            print("GRAPHRAG CONDENSED CONTEXT")
            print("="*80)
            print(graphrag_output.get("answer", "No condensed context found."))
            print("="*80 + "\n")
            print("DEBUG PROLOG-GRAPHRAG:Transferring evidence to Prolog engine...\n")
            condensed_context = graphrag_answer
            raw_context_strings = graphrag_retriever_results
        else:
            condensed_context = ""
            raw_context_strings = []
            
        # ── Split KBPedia vs Wikidata retrieved items ────────────────────────────
        if isinstance(raw_context_strings, list):
            kbpedia_items = []
            wikidata_items = []
            for item in graphrag_retriever_results:
                src = ""
                if hasattr(item, "metadata"):
                    src = (item.metadata or {}).get("source", "")
                elif isinstance(item, dict):
                    src = item.get("metadata", {}).get("source", "")
                item_str = str(item)
                raw_context_strings.append(item_str)
                if src == "Wikidata":
                    wikidata_items.append(item_str)
                else:
                    kbpedia_items.append(item_str)

            if SKIP_LOGICAL_EVIDENCE_LLM:
                # Bypass the GRAPHRAG_TEMPLATE LLM step — pass raw triples directly to Prolog.
                # This is richer and avoids the intermediate LLM bottleneck.
                retrieved_context_str = "\n".join(raw_context_strings)
                print("DEBUG PROLOG-GRAPHRAG:SKIP_LOGICAL_EVIDENCE_LLM=True — passing raw triples to Prolog.")
            else:
                # Default: use the LLM-distilled logical evidence text as context
                retrieved_context_str = condensed_context if graphrag_output else ""
            # Append Wikidata facts to context_from_prompt so they reach the synthesis LLM
            if wikidata_items:
                wikidata_block = "\n\nWikidata Background Facts (for context, not Prolog logic):\n" + "\n".join(wikidata_items)
                # context_from_prompt = (context_from_prompt or "") + wikidata_block
        else:
            retrieved_context_str = raw_context_strings

        pgr_results = {}
        prolog_error, explainer_output, final_answer = None, None, None
        llm_logprobs = []
        if fallback == "prolog-graphrag":
            try:
                pgr_results = prolog_driver.run_pipeline(question=question, retrieved_context=condensed_context, status_callback=status_callback) if flag != "q" else None
            except Exception as e:
                prolog_error = f"Error occurred while running Prolog pipeline: {e}"
            else:
                explainer_output = pgr_results.get("explainer_output", "") if pgr_results else ""
                if status_callback:
                    status_callback({"type": "step", "step": 7})
                llm_output = generate(question, retrieved_context_str, explainer_output, flag=flag, sample_mode=sample_mode, fallback=fallback, status_callback=status_callback) if prolog_error is None else pgr_results.get("final_answer", "")
                final_answer = llm_output.get("text_answer", {"text_answer": "Error generating answer"}) if llm_output else {"text_answer": "Error generating answer"}
                llm_logprobs = llm_output.get("logprobs", []) if llm_output else {}
        else:
            prolog_error = "Pipeline decided to fallback to GraphRAG, skipping Prolog execution."
            explainer_output = "No explainer output since Prolog was skipped."

            final_answer = graphrag_output.get("answer", {"text_answer": "Error generating answer"}) if graphrag_output else {"text_answer": "Error generating answer"}

        logprobs = llm_logprobs if fallback == "prolog-graphrag" else graphrag_logprobs
        print(f"PROLOG ERROR: {prolog_error}" if prolog_error else "Prolog executed successfully without errors.")
        print(f"**FINAL LLM OUTPUT: \n{final_answer}**")
        end_time = time.perf_counter()
        duration = end_time - start_time
        print(f"====The pipeline executed in {duration:.4f} seconds. Prolog verified: {prolog_error is None}===")
        
        if not sample_mode:
            return {
                "answer": final_answer if final_answer else "Error generating answer",
                "logprobs": logprobs,
                "database": pgr_results.get("database", "") if pgr_results else "No database generated.",
                "prolog_query": pgr_results.get("query", "") if pgr_results else "No prolog query generated.",
                "query": query,
                "condensed_context": condensed_context,
                "contexts": retrieved_context_str,
                "prolog_explanation": pgr_results.get("prolog_explanation", "") if pgr_results else "",
                "explainer_output": pgr_results.get("explainer_output", "") if pgr_results else "No explainer output generated.",
                "prolog_error": pgr_results.get("prolog_error") if pgr_results else None,
                "fallback": fallback
            }
        else:
            # NOTE: sample_mode MUST BE TRUE for all pipeline calls for the semantic entropy calculation to be carried out with each prompt
            answers = [output["text_answer"] for output in llm_output],
            logprobs =  [output["logprobs"] for output in llm_output],
            se_results = compute_semantic_entropy(llm_output)
            return {
                "answers": answers,
                "logprobs": logprobs,
                "best_answer": se_results["best_answer"],
                "semantic_entropy": se_results["semantic_entropy"],
                "hallucination_flag": se_results["hallucination_flag"],
                "database": pgr_results.get("database", "") if pgr_results else "No database generated.",
                "prolog_query": pgr_results.get("query", "") if pgr_results else "No prolog query generated.",
                "query": query,
                "condensed_context": condensed_context,
                "contexts": retrieved_context_str,
                "prolog_explanation": pgr_results.get("prolog_explanation", "") if pgr_results else "",
                "explainer_output": pgr_results.get("explainer_output", "") if pgr_results else "No explainer output generated.",
                "prolog_error": pgr_results.get("prolog_error") if pgr_results else None,
                "fallback": fallback
            }

    
def run_graphrag_pipeline(question: str, use_global_kg: bool = False, status_callback=None) -> dict:
    """Wrapper function to run the entire pipeline with a given prompt and flag."""
    return run_pipeline(question, flag="", use_global_kg=use_global_kg, status_callback=status_callback)

if __name__ == "__main__":
    prompt = "Which of the following parts of a plant cell has a function that is most similar to the function of an animal skeleton?"
    print(f"--- Running Pipeline with prompt: '{prompt}' ---")
    # flag default to empty string to run everything
    output = run_pipeline(prompt, flag="x")
    print("\n--- Final Answer ---")
    print(output.get("answer"))