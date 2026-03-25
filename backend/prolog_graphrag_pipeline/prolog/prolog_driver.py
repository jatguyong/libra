"""Prolog reasoning driver — interfaces with s(CASP) via Janus-SWI.

Orchestrates the full Prolog sub-pipeline:
  1. Load the s(CASP) solver (auto-installing it if needed).
  2. Generate Prolog code from the question and retrieved context.
  3. Validate the code against Janus-SWI and run the s(CASP) solver.
  4. Extract a human-readable proof explanation and truth value.

Results are returned as a dict consumed by ``main_driver.run_pipeline()``.
"""
import janus_swi as janus
import re
import os
import time
import logging
from typing import Optional
from .prolog_generator import generate_prolog_code, capture_db_and_query, capture_predicate_and_arguments
from .explainer import generate_safe_scasp_wrapper, generate_explanation
from .. import llm

logger = logging.getLogger(__name__)

SCASP_AVAILABLE = False
ALLOW_LLM_FALLBACK = True   # Enables LLM synthesis fallback when Prolog generation fails

# ── Persistent Prolog debug log (file handler) ────────────────────────────
def _setup_prolog_file_logger():
    """Add a file handler to the package logger for persistent Prolog debug output.

    Replaces the old _TeeLogger approach that hijacked sys.stdout, which
    was fragile and could interfere with other libraries.
    """
    _log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
    os.makedirs(_log_dir, exist_ok=True)
    _log_path = os.path.join(_log_dir, "debug_prolog_output.txt")

    # Avoid duplicate handlers on reimport
    pkg_logger = logging.getLogger("prolog_graphrag_pipeline")
    if not any(isinstance(h, logging.FileHandler) and h.baseFilename == os.path.abspath(_log_path) for h in pkg_logger.handlers):
        fh = logging.FileHandler(_log_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s: %(message)s"))
        pkg_logger.addHandler(fh)

_setup_prolog_file_logger()
# ─────────────────────────────────────────────────────────────────────────────

def use_scasp():
    """Load the s(CASP) solver, installing it first if necessary."""
    global SCASP_AVAILABLE
    if SCASP_AVAILABLE:
        return
        
    try:
        # Try to load first
        list(janus.query("use_module(library(scasp))."))
        janus.query_once("use_module(library(scasp/human)).")
        SCASP_AVAILABLE = True
    except Exception:
        logger.info("s(CASP) not found locally. Attempting installation...")
        try:
            janus.query_once("pack_install(scasp, [interactive(false)]).")
            list(janus.query("use_module(library(scasp))."))
            janus.query_once("use_module(library(scasp/human)).")
            logger.info("s(CASP) installed and loaded successfully.")
            SCASP_AVAILABLE = True
        except Exception as e:
            logger.error("Failed to install or load s(CASP): %s", e)
            SCASP_AVAILABLE = False

def run_pipeline(question: str, retrieved_context: str, status_callback=None) -> dict:
    """Execute the full Prolog reasoning sub-pipeline.

    Args:
        question: The user's natural-language question.
        retrieved_context: Concatenated text from the GraphRAG retriever.
        status_callback: Optional callable for SSE progress updates.

    Returns:
        Dict with keys ``explainer_output``, ``prolog_explanation``,
        ``database``, ``query``, ``prolog_error``, etc.
    """
    start_time = time.perf_counter()
    
    # Ensure s(CASP) is loaded
    if not SCASP_AVAILABLE:
        use_scasp()
    # Ensure inputs are strings
    if isinstance(retrieved_context, list):
        retrieved_context = "\n".join(retrieved_context)
    if not retrieved_context:
        retrieved_context = ""
    

    logger.info("User Question: %s", question)
    


    final_context = retrieved_context + "\n"

    prolog_error: str | None = None  # None = success; str = error message on failure
    database, query, explainer_output, human_readable_explanation, prolog_error = None, None, None, None, None
    retrieved_values = ""

    # ── Attempt Prolog-verified path ───────────────────────────────────
    try:
        if status_callback:
            status_callback({"type": "step", "step": 5})
            
        database, query = generate_prolog_code(
            question=question,
            retrieved_context=final_context,
            most_recent_error=None,
        )

        if status_callback and database:
            db_lines = len(database.strip().split("\n"))
            status_callback({"type": "thought", "step": 5, "message": f"I translated the context into {db_lines} lines of formal executable Prolog logic and formulated the target logical query as: '{query}'."})

        if not SCASP_AVAILABLE:
            raise RuntimeError("s(CASP) library is specifically required for this pipeline. Execution aborted.")

        wrapper = ""

        wrapper = generate_safe_scasp_wrapper(query)
        final_query = f"explain(Explanation)."
        
        if status_callback:
            status_callback({"type": "step", "step": 6})
            status_callback({"type": "thought", "step": 6, "message": "I forwarded the formal query and knowledge base to the SWI-Prolog s(CASP) engine for rigorous verification."})
            
        logger.debug("Consulting database...")
        janus.consult("user", database + "\n" + wrapper)
        try:
            result = janus.query_once(final_query)
            logger.debug("Query Results: %s", result)
            
            if result:
                for arg in result.keys():  
                    if arg not in ["Explanation", "Tree", "Model"] and (arg.isupper() or arg == "truth"):  
                        val = result[arg]
                        logger.debug("%s Found: %s", arg, val)
                        retrieved_values += f"{arg}: {val} "
                        # Capture specifically which multiple-choice letter was proven
                
                if status_callback:
                    if retrieved_values.strip():
                        status_callback({"type": "thought", "step": 6, "message": f"Engine execution completed. I derived a mathematical proof for: {retrieved_values.strip()}."})
                    else:
                        status_callback({"type": "thought", "step": 6, "message": "Engine execution completed. I successfully derived a mathematical proof."})

                if SCASP_AVAILABLE and 'Explanation' in result:
                    human_readable_explanation = result['Explanation']
                    logger.debug("Human-Readable Explanation: %s", human_readable_explanation)
            else:
                logger.warning("Prolog query returned no solution.")
                if status_callback:
                    status_callback({"type": "thought", "step": 6, "message": "Engine execution completed, but I couldn't derive a mathematically verifiable proof from the given context."})
        except Exception as e:
            logger.error("Prolog query error: %s", e)
            if status_callback:
                status_callback({"type": "thought", "step": 6, "message": f"The s(CASP) engine encountered an error during proof derivation: {e}"})
            
        if status_callback:
            status_callback({"type": "step", "step": 7})
            
        explainer_output = generate_explanation(
            question=question,
            retrieved_context=retrieved_context,
            database=database,
            query=query,
            retrieved_values=retrieved_values,
            human_readable_explanation=human_readable_explanation,
        )
        if status_callback:
            status_callback({"type": "thought", "step": 7, "message": "I decoded the highly technical Prolog proof tree into a format ready for natural language interpretation."})
        if not explainer_output:
            logger.error("Explainer failed to generate output.")
    except Exception as gen_err:
        # ── Graceful fallback: Prolog generation failed ──────────────────────
        prolog_error = str(gen_err)
        logger.warning("Prolog failed: %s — falling back to unverified GraphRAG answer.", prolog_error)
        explainer_output = None  # No Prolog proof; LLM will answer from context alone
        if not ALLOW_LLM_FALLBACK:
            raise gen_err
    final_answer = None
    # ── Final synthesis (always runs unless fallback disabled) ───────────────
    if prolog_error and not ALLOW_LLM_FALLBACK:
        logger.warning("LLM fallback disabled: skipping final synthesis because Prolog failed.")
        final_answer = {"text_answer": "Error: Prolog generation failed and LLM fallback is disabled."}
    else:
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

    for test in tests[:1]:
        decoder_explanation = run_pipeline(test["question"], test["context"], "")