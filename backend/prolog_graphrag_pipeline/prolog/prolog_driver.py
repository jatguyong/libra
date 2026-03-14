import janus_swi as janus
import re
import sys
import os
import time
from typing import Optional
from .prolog_generator import generate_prolog_code, capture_db_and_query, capture_predicate_and_arguments
from .explainer import generate_safe_scasp_wrapper, generate_explanation
from .prolog_llms import warmup_prolog_model, reset_kv_cache_flag
from .. import llm

SCASP_AVAILABLE = False
ALLOW_LLM_FALLBACK = True   # Enables LLM synthesis fallback when Prolog generation fails

# ── Dedicated Prolog debug log ────────────────────────────────────────────────
class _TeeLogger:
    """Writes to both the original stream and a log file simultaneously."""
    def __init__(self, original_stream, log_path: str):
        self._orig = original_stream
        self._log = open(log_path, "a", encoding="utf-8", errors="replace", buffering=1)

    def write(self, msg):
        self._orig.write(msg)
        self._log.write(msg)

    def flush(self):
        self._orig.flush()
        self._log.flush()

    def isatty(self):
        return getattr(self._orig, "isatty", lambda: False)()

    def fileno(self):
        return self._orig.fileno()

def _install_prolog_logger():
    """Install the TeeLogger on stdout if not already installed for this process."""
    if isinstance(sys.stdout, _TeeLogger):
        return  # Already installed
    _log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
    os.makedirs(_log_dir, exist_ok=True)
    _log_path = os.path.join(_log_dir, "debug_prolog_output.txt")
    sys.stdout = _TeeLogger(sys.stdout, _log_path)
    sys.stderr = _TeeLogger(sys.stderr,
                            os.path.join(_log_dir, "prolog_debug.txt"))

_install_prolog_logger()
# ─────────────────────────────────────────────────────────────────────────────

def use_scasp():
    global SCASP_AVAILABLE
    if SCASP_AVAILABLE:
        return
        
    # print("Attempting to load s(CASP)...")
    try:
        # Try to load first
        list(janus.query("use_module(library(scasp))."))
        janus.query_once("use_module(library(scasp/human)).")
        # print("s(CASP) loaded successfully.")
        SCASP_AVAILABLE = True
    except Exception:
        print("s(CASP) not found locally. Attempting installation...")
        try:
            janus.query_once("pack_install(scasp, [interactive(false)]).")
            list(janus.query("use_module(library(scasp))."))
            janus.query_once("use_module(library(scasp/human)).")
            print("s(CASP) installed and loaded successfully.")
            SCASP_AVAILABLE = True
        except Exception as e:
            print(f"CRITICAL ERROR: Failed to install or load s(CASP): {e}")
            SCASP_AVAILABLE = False

def run_pipeline(question: str, retrieved_context: str, status_callback=None) -> dict:
    start_time = time.perf_counter()
    
    # Ensure s(CASP) is loaded
    if not SCASP_AVAILABLE:
        use_scasp()
    # Ensure inputs are strings
    if isinstance(retrieved_context, list):
        retrieved_context = "\n".join(retrieved_context)
    if not retrieved_context:
        retrieved_context = ""
    

    print(f"**User Question:**\n{question}")
    
    # Safely print retrieved context to avoid Windows charmap encoding errors with chars like \u2192 (→)
    safe_context = retrieved_context.encode('utf-8', errors='replace').decode('utf-8')
    # print(f"**Retrieved Context:**\n{safe_context}")

    # Re-prime Ollama's KV cache with the static few-shot prefix.
    # GraphRAG (same model) runs just before us and evicts the cache.
    # Resetting the flag then calling warmup ensures all retry attempts
    # within this question benefit from the cached prefix.
    reset_kv_cache_flag()
    warmup_prolog_model()

    # print("Generating Prolog...")
    final_context = retrieved_context + "\n"

    prolog_error: str | None = None  # None = success; str = error message on failure
    database, query, explainer_output, human_readable_explanation, prolog_error = None, None, None, None, None
    retrieved_values = ""

    # ── Attempt Prolog-verified path ───────────────────────────────────
    try:
        if status_callback:
            status_callback({"type": "step", "step": 4})
            
        database, query = generate_prolog_code(
            question=question,
            retrieved_context=final_context,
            most_recent_error=None,
        )
        # print(f"**Extracted database:**\n{database}")
        # print(f"**Extracted query:**\n{query}")

        if not SCASP_AVAILABLE:
            raise RuntimeError("s(CASP) library is specifically required for this pipeline. Execution aborted.")

        wrapper = ""

        # print("Generating s(CASP) wrapper...")
        wrapper = generate_safe_scasp_wrapper(query)
        # print(f"**Wrapper:** \n{wrapper}")
        final_query = f"explain(Explanation)."
        
        if status_callback:
            status_callback({"type": "step", "step": 5})
            
        print("Consulting database...", flush=True)
        janus.consult("user", database + "\n" + wrapper)
        try:
        # if True:
            # print("Querying database...", flush=True)
            result = janus.query_once(final_query)
            print(f"**Query Results:** \n{result}", flush=True)
            
            if result:
                for arg in result.keys():  
                    if arg not in ["Explanation", "Tree", "Model"] and (arg.isupper() or arg == "truth"):  
                        val = result[arg]
                        print(f"{arg} Found: {val}")    
                        retrieved_values += f"{arg}: {val} "
                        # Capture specifically which multiple-choice letter was proven
                
                if SCASP_AVAILABLE and 'Explanation' in result:
                    print("**Human-Readable Explanation**")
                    human_readable_explanation = result['Explanation']
                    print(human_readable_explanation)
            else:
                print("No solution found.")
        except Exception as e:
        # else:
            print(f"Error: {e}")
            
        if status_callback:
            status_callback({"type": "step", "step": 6})
            
        explainer_output = generate_explanation(
            question=question,
            retrieved_context=retrieved_context,
            database=database,
            query=query,
            retrieved_values=retrieved_values,
            human_readable_explanation=human_readable_explanation,
        )
        if explainer_output:
            # print(f"**Explainer Output:** \n{explainer_output}")
            pass
        else:
            print("ERROR: Explainer failed to generate output.")
    # else:
    except Exception as gen_err:
        # ── Graceful fallback: Prolog generation failed ──────────────────────
        prolog_error = str(gen_err)
        print(f"[Prolog FAILED] {prolog_error} — falling back to unverified GraphRAG answer.")
        explainer_output = None  # No Prolog proof; LLM will answer from context alone
        if not ALLOW_LLM_FALLBACK:
            raise gen_err
    final_answer = None
    # ── Final synthesis (always runs unless fallback disabled) ───────────────
    if prolog_error and not ALLOW_LLM_FALLBACK:
        print("\n**LLM FALLBACK DISABLED: Skipping final synthesis because Prolog failed.")
        final_answer = {"text_answer": "Error: Prolog generation failed and LLM fallback is disabled."}
    else:
        # print("\n**FINAL LLM OUTPUT:")
        final_answer = llm.generate(question, retrieved_context, explainer_output=None, flag="synthesis", fallback=True, status_callback=status_callback)

    
    result_dict = {
        "final_answer": None if prolog_error else final_answer,
        "database": database if database else "No database correctly generated.",
        "query": query if query else "No query correctly generated.",
        "prolog_explanation": human_readable_explanation if human_readable_explanation else "No s(cASP) explanation generated.",
        "explainer_output": explainer_output if explainer_output else "No explainer output correctly generated",
        "prolog_error": prolog_error if prolog_error else None
    }
    return result_dict


if __name__ == "__main__":
    tests = [
        {
            "question": "Who is Alice's brother?",
            "context": "Bob is Alice's brother. Amanda is Alice's sister.",
            "database": rf"""
    male(bob).
    female(alice).
    female(amanda).
    parent(p1, bob).
    parent(p1, alice).
    parent(p1, amanda).
    sibling(Sibling1, Sibling2) :- parent(Parent, Sibling1), parent(Parent, Sibling2), Sibling1 \= Sibling2.
    brother(Brother, Sibling) :- male(Brother), sibling(Brother, Sibling).
            """,
            "query": rf"brother(Brother, amanda)."
        },
        
        # Example 2
        {
            "question": "Is Maria the grandmother of Dan?",
            "context": "Maria is the mother of Chloe. Chloe is the mother of Dan.",
            "database": rf"""
    parent(maria, chloe). 
    parent(chloe, dan). 
    grandmother(Grandmother, Grandchild) :- parent(Grandmother, IntermediateParent), parent(IntermediateParent, Grandchild). 
    """,
            "query": rf"grandmother(maria, dan). "
        },
        
        # Example 3
        {
            "question": "Who does Vito believe he should keep closer?",
            "context": "Tomasinno is the friend of Vito. Solozzo is the enemy of Vito. Vito believes that he should keep his enemies closer than his friends.",
            "database": rf"""
    friend(tomasinno, vito).
    enemy(solozzo, vito).
    closer_than(Enemy, Friend) :- enemy(Enemy, vito), friend(Friend, vito).
    vito_keeps_closer(Person) :- closer_than(Person, _). 
    """,
            "query": rf"vito_keeps_closer(Who)."
        },
        
        # Example 4:
        {
            "question": "Is every square a rectangle?",
            "context": "A square is a polygon with four equal sides and four right angles. A rectangle has four right angles.",
            "database": rf"""
    has_property(square, four_equal_sides). 
    has_property(square, four_right_angles). 
    is_a(square, polygon). 
    is_a(Shape, rectangle) :- has_property(Shape, four_right_angles). 
    """,
            "query": rf"is_a(square, rectangle)."
        },
        
        # Example 5
        {
            "question": "If the grass is contaminated, are the snakes affected?",
            "context": "In a food web, grass is a producer. Grasshoppers eat grass. Frogs eat grasshoppers. Snakes eat frogs.",
            "database": rf"""
    eats(grasshopper, grass). 
    eats(frog, grasshopper). 
    eats(snake, frog). 
    is_producer(grass). 
    is_contaminated(grass). 
    affected(Species) :- is_contaminated(Species). 
    affected(Predator) :- eats(Predator, Prey), affected(Prey). 
    """,
            "query": rf"affected(snake)."
        },
    ]

    use_scasp()
    # Calculate the path to the directory you want to import from.
    # '..' refers to the parent directory.

    for test in tests[:1]:
        decoder_explanation = run_pipeline(test["question"], test["context"], "")
    
# question = "Will prices go up if people are reluctant to take out loans?"
# retrieved_context = "When interest rates are high, people will be less likely to take out loans. When people take less loan out, demand for goods decrease. When demand for goods decrease, interest rates spike up. Prices go down when demand is down."
# run_prolog_pipeline(question, retrieved_context)

# question = "Who does Vito believe he should keep closer?"
# retrieved_context = "Tomasinno is the friend of Vito. Solozzo is the enemy of Vito. Vito believes that he should keep his enemies closer than his friends."
# run_prolog_pipeline(question, retrieved_context)

# question = "If the grass is contaminated, are the snakes affected?"
# retrieved_context = "In a food web, grass is a producer. Grasshoppers eat grass. Frogs eat grasshoppers. Snakes eat frogs. "
# run_prolog_pipeline(question, retrieved_context)

        
        
    

        
    
    
    