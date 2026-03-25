import janus_swi as janus
import re
import sys


def _sanitize_multiword_atoms(code: str) -> str:
    """Syntax-safety net: ensure all predicate arguments are valid Prolog atoms.

    ONLY converts spaces→underscores and lowercases multi-word phrases to prevent
    'Syntax error: Operator expected'. Does NOT condense or truncate atoms —
    that is the Prolog generator LLM's job via the system prompt instruction
    'Condense long phrases into 3-5 critical words'.

    Handles:
      - Spaces in lowercase atom:   'choice(a, cell membrane)'  → 'choice(a, cell_membrane)'
      - Capitalized sentence atom:  'choice(a, Liquid water)'   → 'choice(a, liquid_water)'
      - Single-word Prolog variable: 'CellPart', 'X', '_'      → unchanged (variable)
    """
    def _fix_args(match: re.Match) -> str:
        pred = match.group(1)
        open_p = match.group(2)
        args_str = match.group(3)
        close_p = match.group(4)

        new_args = []
        for arg in args_str.split(','):
            arg = arg.strip()
            if not arg:
                continue

            # Single-word uppercase/underscore-prefixed token → Prolog variable, leave as-is
            is_variable = (arg[0].isupper() or arg[0] == '_') and ' ' not in arg
            if is_variable:
                new_args.append(arg)
                continue

            # Already single-quoted → leave as-is
            if arg.startswith("'") or arg.startswith('"'):
                new_args.append(arg)
                continue

            # Fix spaces (including capitalized multi-word phrases)
            if ' ' in arg or (arg[0].isupper()):
                arg = re.sub(r'\s+', '_', arg).lower()

            new_args.append(arg)
        return f"{pred}{open_p}{', '.join(new_args)}{close_p}"

    return re.sub(r'([a-z_][a-z0-9_]*)(\()([^()]+)(\))', _fix_args, code)



def capture_db_and_query(answer_text: str) -> tuple[str, str]:
    import re

    # Match everything after <database> until either </database>, <query>, or the end of the string
    db_match = re.search(r"<database>(.*?)(?:</database>|<query>|\Z)", answer_text, re.DOTALL | re.IGNORECASE)
    
    # Match everything after <query> until </query>, </reasoning_step> (common hallucination), or the end of the string
    query_match = re.search(r"<query>(.*?)(?:</query>|</reasoning_step>|\Z)", answer_text, re.DOTALL | re.IGNORECASE)

    if not db_match:
        raise ValueError("Database not found in LLM's response. Ensure you wrap your facts and rules strictly inside `<database>` tags.")
    db = db_match.group(1).strip()

    if not query_match:
        raise ValueError("Query not found in LLM's response. Ensure you wrap your goal strictly inside `<query>` tags.")
    query = query_match.group(1).strip()

    # Sanitize multi-word atoms (e.g. "cell membrane" -> "cell_membrane")
    db = _sanitize_multiword_atoms(db)
    query = _sanitize_multiword_atoms(query)

    return {"database": db, "query": query}


def capture_predicate_and_arguments(query: str) -> dict:
    
    predicate_match = re.search(r"(\w+)\s*\(", query)
    try:
        predicate = predicate_match.group(1)
    except:
        raise ValueError("Could not extract predicate name from query")
    
    query = query.replace(".", "").replace("\n", "")
    while query.count("(") > 0 and query.count("(") == query.count(")"):
        ei = query.find("(")
        logger.debug(f"prefix: {query[:ei+1]}")
        query = query.replace(query[:ei+1], "").removesuffix(")")
    
    arguments_match = re.search(r"\((.*?)\)", query)
    try:
        arguments = arguments_match.group(1).replace(" ", "").split(",")
        print("Extracted Arguments:", arguments)
    except:
        raise ValueError("Could not extract arguments from query")
    return {"predicate": predicate, "arguments": arguments}

def _inject_inline_errors(code: str, last_error: str) -> str:
    if not code:
        return code
        
    lines = code.split('\n')
    new_lines = []
    
    # Extract "Unknown procedure: name/arity"
    unknown_match = re.search(r"Unknown procedure: ([a-zA-Z0-9_]+)/(\d+)", last_error)
    missing_pred = unknown_match.group(1) if unknown_match else None
    
    # Extract forbidden pattern (e.g. Disjunction ';' is forbidden)
    forbidden_match = None
    if "is forbidden" in last_error:
        # Check for ';' specifically as it's the most common repeat offender
        if "';'" in last_error or "Disjunction" in last_error:
            forbidden_match = ';'
        else:
            m = re.search(r"'(.+?)'\s+is forbidden", last_error)
            if m:
                forbidden_match = m.group(1)
            elif "arithmetic '>='" in last_error:
                forbidden_match = '>='
            elif "arithmetic '<='" in last_error:
                forbidden_match = '<='
            elif "arithmetic '>'" in last_error:
                forbidden_match = '>'
            elif "arithmetic '<'" in last_error:
                forbidden_match = '<'
            elif "Evaluation 'is'" in last_error:
                forbidden_match = 'is'

    # Extract Singleton variables: [Var1, Var2]
    singleton_vars = []
    if "Singleton variables" in last_error:
        m = re.search(r"Singleton variables: \[([^\]]+)\]", last_error)
        if m:
            singleton_vars = [v.strip() for v in m.group(1).split(',')]

    # Extract Discontiguous predicate: "Clauses of x/1 are not together"
    discontiguous_pred = None
    if "are not together" in last_error or "discontiguous" in last_error.lower():
        m = re.search(r"Clauses of ([a-zA-Z0-9_]+)/(\d+) are not together", last_error)
        if m:
            discontiguous_pred = m.group(1)

    for line in lines:
        needs_comment = False
        comment_text = ""
        
        # Strip comments for the search to avoid double-commenting
        content_only = re.sub(r"%.*$", "", line).strip()
        if not content_only:
            new_lines.append(line)
            continue

        if missing_pred and re.search(rf"\b{missing_pred}\(", content_only):
            needs_comment = True
            comment_text = f"% ERROR TRIGGERED HERE: You called '{missing_pred}' but it is NEVER defined as a fact or rule."
            
        elif discontiguous_pred and (content_only.startswith(f"{discontiguous_pred}(") or discontiguous_pred in content_only):
            needs_comment = True
            comment_text = f"% ERROR TRIGGERED HERE: Predicate '{discontiguous_pred}' is scattered. MOVE all clauses of '{discontiguous_pred}' together in one block."

        elif forbidden_match and forbidden_match in content_only:
            needs_comment = True
            comment_text = f"% ERROR TRIGGERED HERE: REMOVE THIS FORBIDDEN OPERATOR '{forbidden_match}'."
            if forbidden_match == ';':
                comment_text += " Disjunction is forbidden. Use multiple separate rules instead."
            elif forbidden_match in ['>=', '<=', '>', '<']:
                correct = {'+': '#+', '-': '#-', '>=': '#>=', '<=': '#=<', '>': '#>', '<': '#<'}.get(forbidden_match, '#=')
                comment_text += f" Use '{correct}' for s(CASP) constraint arithmetic."
            elif forbidden_match == 'is':
                comment_text += " Use '#=' for s(CASP) constraint assignment."
            
        elif singleton_vars and ":-" in content_only:
            for v in singleton_vars:
                if re.search(rf"\b{v}\b", content_only):
                    needs_comment = True
                    comment_text = f"% ERROR TRIGGERED HERE: Variable '{v}' is a singleton (only used once). Replace with '_' or use it again."
                    break

        if needs_comment:
            new_lines.append(comment_text)
        new_lines.append(line)
        
    return "\n".join(new_lines)


def generate_prolog_generation_prompt(question: str, retrieved_context: str, error_history: list, previous_code: str = None, question_type: str = "freeform") -> str:
    prompt = f"""Now, process the following:
User Question:
{question}

Context:
{retrieved_context}
"""

    if question_type == "mcq":
        prompt += """
CRITICAL REMINDER — LETTER ASSIGNMENT:
Re-read the User Question above carefully. The choices are labeled exactly as they appear (A, B, C, D).
Your `choice/2` facts MUST encode each letter to EXACTLY the choice text it corresponds to in the question.
Your `answer(OptionLetter)` rule MUST unify with the letter whose choice text satisfies the criteria — NOT any other letter.
Before writing <database>, double-check: does `answer(X)` fire for the correct letter?
"""
    elif question_type == "binary":
        prompt += """
CRITICAL REMINDER — QUESTION TYPE: BINARY
This is a yes/no question. You MUST NOT use `choice/2` facts or `answer(OptionLetter)` queries.
Define grounded instances from the question, write rules for the condition, then query the fully grounded relationship directly.
"""
    else:  # freeform
        prompt += """
CRITICAL REMINDER — QUESTION TYPE: FREEFORM/EXPLANATORY
This is an explanatory or conceptual question. There are NO multiple-choice options.
You MUST NOT use `choice/2` facts or `answer(OptionLetter)` queries.
Define facts and rules from the context, then query the primary target entity state — use a Prolog variable to capture the answer if needed (e.g., `particle_comparison(co2, nh3, Relationship).`).
"""

    if error_history:
        # Deduplicate error history for printing so prompt isn't bloated
        unique_errors = []
        for e in error_history:
            if not unique_errors or unique_errors[-1] != e:
                unique_errors.append(e)
        numbered = "\n".join(f"  [{i+1}] {e}" for i, e in enumerate(unique_errors))

        # Check consecutive identical errors
        last_error = error_history[-1]
        same_error_count = 0
        for e in reversed(error_history):
            if e == last_error:
                same_error_count += 1
            else:
                break
                
        penalty_prompt = ""
        if same_error_count >= 2:
            penalty_prompt = f"\n!!! PERSISTENT ERROR: You failed to fix this {same_error_count}x. PREVIOUS CODE IS BLOCKED. Fix or remove lines with '% ERROR TRIGGERED HERE'.\n"


        # ── Targeted example-driven guidance keyed to the last error ──────
        last_error = error_history[-1]
        targeted_fix = ""

        if "query" in last_error.lower() and ":-" in last_error:
            targeted_fix = """
WRONG (rule in <query>): <query> answer(X) :- choice(X, T). </query>
CORRECT (rule in <database>): <database> answer(X) :- choice(X, T). </database> <query> answer(X). </query>
"""
        elif "Unknown procedure" in last_error:
            targeted_fix = """
WRONG: answer(X) :- undefined(X).
CORRECT: has_prop(X). answer(X) :- has_prop(X). (every body predicate MUST be defined)
"""
        elif "choice" in last_error.lower() and "UPPERCASE" in last_error:
            targeted_fix = "WRONG: choice(a, A). CORRECT: choice(a, atom_text). (use grounded lowercase atoms)\n"
        elif "Disjunction" in last_error or "';'" in last_error:
            targeted_fix = "WRONG: a :- b ; c. CORRECT: a :- b. a :- c. (NO disjunction)\n"
        elif "Singleton variables" in last_error:
            targeted_fix = "WRONG: a(X) :- b(X, Y). CORRECT: a(X) :- b(X, _). (use _ for singletons)\n"
        elif "time_limit_exceeded" in last_error or "infinite loop" in last_error.lower():
            targeted_fix = "WRONG: a :- a, b. CORRECT: a. a :- b, a. (recursive rules need ground base cases)\n"

        prompt += f"""
### ERRORS TO FIX
{numbered}
{targeted_fix}
Rewrite ENTIRE <database> and <query>. <database> must have rules (:-); <query> exactly one plain goal.
"""
        if previous_code:
            annotated_code = _inject_inline_errors(previous_code, last_error)
            prompt += f"""
{penalty_prompt}
### PREVIOUS CODE (FIX MARKED LINES):
<database>
{annotated_code}
</database>
"""

    return prompt

from typing import Optional


def _ask_if_close_to_fixing(generate_fn, most_recent_error: str) -> bool:
    """
    Ask the LLM whether the last Prolog error looks easily fixable.
    Returns True if the LLM thinks so (→ grant 5 more attempts),
    False otherwise (→ raise immediately).
    """
    close_check_prompt = f"""You are evaluating a Prolog code generation failure.

The last error encountered was:
{most_recent_error}

Is this error likely fixable with one or two small adjustments to the Prolog code?
Answer with ONLY one word: YES or NO.
"""
    try:
        result = generate_fn(prompt=close_check_prompt, flag="q")
        if not result:
            return False
        answer_text = result.get("text_answer", "").strip().upper()
        logger.debug(f"[Prolog retry] Close-check answer: {repr(answer_text)}")
        return answer_text.startswith("YES")
    except Exception as e:
        logger.debug(f"[Prolog retry] Close-check LLM call failed: {e}. Skipping extension.")
        return False


def _run_prolog_attempt(generate_fn, i: int, question: str, retrieved_context: str, error_history: list, previous_code: str = None, last_attempt_tracker: list = None, question_type: str = "freeform"):
    """Single attempt of Prolog code generation + validation."""
    prompt = generate_prolog_generation_prompt(question, retrieved_context, error_history, previous_code, question_type)

    try:
        answer = generate_fn(prompt=prompt, flag="prolog", question_type=question_type)
    except TypeError as e:
        logger.error(f"CRITICAL ERROR calling generate: {e}")
        raise e

    if not answer:
        raise ValueError(f"Iteration {i} | LLM returned None.")

    answer_text = answer['text_answer']

    # CLEANING: Remove markdown bullets if LLM hallucinates them
    lines = answer_text.split('\n')
    cleaned_lines = []
    for line in lines:
        clean = line.strip()
        if clean.startswith("- "):
            clean = clean[2:]
        elif clean.startswith("* "):
            clean = clean[2:]
        cleaned_lines.append(clean)
    answer_text = "\n".join(cleaned_lines)

    db_query = capture_db_and_query(answer_text)
    database = db_query["database"]
    query = db_query["query"].strip()

    # VALIDATION: Provide fallback for ?- hallucination
    if query.startswith("?-"):
        query = query[2:].strip()

    # VALIDATION: Ensure Query is not just a number
    if re.match(r"^\d+\.?$", query):
        raise ValueError(f"Invalid Prolog Query: '{query}'. The query must be a Prolog predicate (e.g., 'successor(1, X).'), not a number.")

    # VALIDATION: Query must NOT contain rule definitions (:-) — those belong in <database>
    # Strip comments and quoted strings before checking, to avoid false positives
    query_stripped = re.sub(r"'[^']*'", "''", query)
    query_stripped = re.sub(r"%.*$", "", query_stripped, flags=re.MULTILINE)
    if ":-" in query_stripped:
        raise ValueError(
            "The <query> tag contains a rule definition (with ':-'), but queries must be plain goals. "
            "Rule definitions (Head :- Body.) belong inside <database> tags. "
            "The <query> tag must contain ONLY a single callable goal, e.g.: `answer(X).` or `my_predicate(foo).` "
            "Move the rule bodies to <database> and call the predicate head in <query>."
        )

    # CLEANUP: Strip inline comments (% ...) from the query
    query = re.sub(r"%.*$", "", query, flags=re.MULTILINE).strip()

    # CLEANUP: Keep only the FIRST complete Prolog statement.
    # The LLM sometimes adds multiple goals or comments after the first one.
    # A valid query is exactly one goal ending with '.'.
    first_dot = query.find('.')
    if first_dot != -1:
        query = query[:first_dot + 1].strip()

    # VALIDATION: Ensure Query ends with a period
    if not query.endswith('.'):
        query += "."

    combined_code = database + "\n" + query
    
    # Save ONLY the database block (not the query) so the LLM can cleanly
    # copy all correct facts+rules forward without being confused by the old query.
    if last_attempt_tracker is not None:
        last_attempt_tracker[0] = database

    # VALIDATION: Ensure no unquoted logic symbols exist
    unquoted_code = re.sub(r"'[^']*'", "''", combined_code)
    unquoted_code = re.sub(r"%.*$", "", unquoted_code, flags=re.MULTILINE)

    # VALIDATION: Hard reject choice/2 in non-MCQ mode
    if question_type != "mcq" and "choice(" in unquoted_code:
        raise ValueError(
            f"QUESTION TYPE VIOLATION: This is a '{question_type}' question, NOT multiple-choice. "
            "You MUST NOT use `choice/2` facts or `answer(OptionLetter)` queries. "
            "Remove ALL `choice(...)` facts. Instead, encode domain facts directly and "
            "write a query that tests the target relationship or captures the answer via a Prolog variable."
        )

    # VALIDATION: MCQ Enforce answer/1
    # If the database contains 'choice(', it is a Multiple-Choice Question.
    # Therefore, the query MUST be 'answer(OptionLetter).' to unify against the choices.
    if "choice(" in unquoted_code:
        if "answer(" not in query:
            raise ValueError("Multiple-Choice constraint violation: You defined 'choice/2' facts but your <query> does not use 'answer/1'. "
                             "For MCQs, you MUST define an `answer(OptionLetter) :- ...` rule in the <database> "
                             "and your <query> MUST be exactly `answer(OptionLetter).` to unify with the correct choice.")
        
        # Check for ungrounded choice facts: e.g. choice(a, A). or choice(A, b).
        # We look for choice( followed by anything, where either argument starts with an Uppercase letter.
        if re.search(r"choice\([a-z]+,\s*[A-Z_][a-zA-Z0-9_]*\)\.", unquoted_code):
            raise ValueError("Multiple-Choice constraint violation: Your 'choice(letter, Description).' facts use UPPERCASE variables for the description (e.g., `choice(a, A).`). "
                             "The description MUST be a grounded LOWERCASE atom based on the actual option text (e.g., `choice(a, lowercase_option_text).`). "
                             "Uppercase variables will unify with anything and break the proof!")


    forbidden_patterns = [
        (r';', "Disjunction ';' is forbidden in s(CASP). Use multiple separate rules with the same head instead of ';'."),
        (r'=:=', "Arithmetic equality '=:=' is forbidden in s(CASP). Use '#=' for constraint arithmetic or '=' for unification."),
        (r'=\\=', "Arithmetic inequality '=\\=' is forbidden in s(CASP). Use '#\\=' for constraint arithmetic."),
        (r'\bis\b', "Evaluation 'is' is forbidden in s(CASP). Use '#=' for constraint arithmetic assignment."),
        # Only match bare < and > that are NOT preceded by # (i.e., not part of #< or #>)
        # Also must not be inside \= or =< (handled separately)
        (r'(?<!#)(?<!=)(?<![<>])(?<![\\])<(?![=<])', "Standard arithmetic less-than '<' is forbidden. Use '#<' instead."),
        (r'(?<!#)(?<!=)(?<![<>])>(?![=])', "Standard arithmetic greater-than '>' is forbidden. Use '#>' instead."),
        # Bare <= and >= (not preceded by # which would make them valid CLP operators)
        (r'(?<!#)<=', "Standard arithmetic '<=' is forbidden. Use '#=<' instead."),
        (r'(?<!#)>=', "Standard arithmetic '>=' is forbidden. Use '#>=' instead."),
        (r'->', "If-then '->' is forbidden in s(CASP). Use separate rules instead."),
        (r'[~⊃∨∧]', "Unquoted logic symbol found. Wrap logical formulas in single quotes or use 'not'/'-' for negation."),
        (r'\\\\\\+', "Negation '\\+' is forbidden in s(CASP). Use 'not' for negation as failure."),
    ]

    for pattern, hint in forbidden_patterns:
        if re.search(pattern, unquoted_code):
            raise ValueError(f"{hint}")



    # NOTE: Wikidata facts for missing KBPedia entities are now retrieved and
    # filtered upstream by kbpedia_retriever.py (ENABLE_WIKIDATA_FALLBACK) and
    # flow into `retrieved_context` as plain text triples — no Q-ID scanning needed here.

    janus.query_once("unload_file(user)")
    janus.consult("user", database)
    # Run query with a 80-second hard timeout to catch infinite recursive loops
    safe_query = f"call_with_time_limit(80, ({query[:-1]}))"
    janus.query_once(safe_query)

    logger.debug(f"Iteration {i} | Prolog code generation success")
    return database, query


def generate_prolog_code(question: str, retrieved_context: str, most_recent_error: Optional[str]) -> tuple:
    """Translate a natural-language question into a valid Prolog database and query.

    Uses the LLM to generate s(CASP)-compatible Prolog code, validates it
    against Janus-SWI, and retries up to 10 times (5 normal + 5 extension)
    with increasingly detailed error feedback.

    Returns:
        (database_str, query_str) on success.

    Raises:
        Exception if all attempts are exhausted.
    """
    import logging as _logging
    _logger = _logging.getLogger(__name__)

    # ── Resolve the generate function once ───────────────────────────────────
    try:
        from .prolog_llms import generate as generate_fn, classify_question_type
    except ImportError:
        from prolog.prolog_llms import generate as generate_fn, classify_question_type

    # ── Classify question type once (before any generation attempt) ──────────
    question_type = classify_question_type(question)
    _logger.info("Detected question type: %r for: %r", question_type, question[:80])

    # ── Shared error handling ────────────────────────────────────────────────

    NORMAL_ATTEMPTS = 5
    EXTENSION_ATTEMPTS = 5
    error_history: list = []
    last_attempt_tracker: list = [None]

    def _record_error(msg: str):
        """Append an error message for the next retry's prompt context."""
        error_history.append(msg)

    def _get_prolog_error_hint(error_str: str) -> str:
        """Map a Janus PrologError message to a targeted fix hint."""
        if "Singleton variables" in error_str:
            return "Use each variable twice or use '_' for singletons."
        if "Syntax error: Operator expected" in error_str:
            return "Wrap mathematical/logical symbols in single quotes."
        if "time_limit_exceeded" in error_str or "Time limit" in error_str:
            return "Infinite loop. Recursive rules must bottom out at ground facts."
        if "not sufficiently instantiated" in error_str:
            return "Use lowercase atoms for facts, not Uppercase variables."
        if "(:-)/2" in error_str or "Rules must be loaded from a file" in error_str:
            return "Rule (:-) in <query>. Move to <database>."
        if "Unknown procedure" in error_str:
            return "Undefined predicate. Every body predicate must be defined as a fact or rule head."
        if "not together" in error_str or "discontiguous" in error_str.lower():
            return "Scattered clauses. Group ALL clauses for the same predicate together."
        return "Ensure strict Prolog syntax. Predicates must be lowercase."

    def _handle_attempt_error(e: Exception, i: int, phase_label: str):
        """Classify an error from _run_prolog_attempt and record it for the next retry.

        Re-raises fatal errors (e.g. missing arguments) immediately.
        """
        if isinstance(e, ValueError):
            err_str = str(e)
            _logger.warning("%s %d | Validation Error: %s", phase_label, i, err_str)
            if "Disjunction" in err_str or "';'" in err_str:
                _record_error(f"{err_str} Forbidden: ';'. Use separate rules.")
            elif "Query not found" in err_str or "strictly inside <query>" in err_str:
                _record_error(f"{err_str} Ensure you output the full <database> AND <query> tags.")
            else:
                _record_error(f"{err_str} Ensure the query is a valid Prolog predicate.")
        elif isinstance(e, janus.PrologError):
            error_str = str(e)
            _logger.warning("%s %d | Prolog Error: %s", phase_label, i, error_str)
            hint = _get_prolog_error_hint(error_str)
            _record_error(f"Prolog Error: {e}\nHint: {hint}")
        else:
            _logger.warning("%s %d | General Error: %s", phase_label, i, e)
            if "missing 3 required positional arguments" in str(e):
                raise e  # Fatal — stop immediately
            if isinstance(e, TimeoutError):
                _record_error(f"LLM call timed out ({e}). The model may have hung — retry.")
            else:
                _record_error(f"Error: {e}. Please ensure valid Prolog syntax.")

    # ── Phase 1: Normal attempts ─────────────────────────────────────────────
    for i in range(NORMAL_ATTEMPTS):
        try:
            return _run_prolog_attempt(generate_fn, i, question, retrieved_context, error_history, last_attempt_tracker[0], last_attempt_tracker, question_type)
        except Exception as e:
            _handle_attempt_error(e, i, "Iteration")

    # ── Phase 2: Extension attempts (if the LLM thinks the error is fixable) ─
    most_recent_error = error_history[-1] if error_history else None

    same_error_count = sum(1 for e in error_history if e == most_recent_error)
    if same_error_count >= 3:
        _logger.warning("Same error repeated %dx — model is stuck. Giving up.", same_error_count)
        raise Exception("Failed to generate valid Prolog code after multiple attempts.")

    _logger.info("Normal attempts exhausted. Asking LLM if error is fixable...")
    if most_recent_error and _ask_if_close_to_fixing(generate_fn, most_recent_error):
        _logger.info("LLM says YES — granting %d extension attempts.", EXTENSION_ATTEMPTS)
        for i in range(NORMAL_ATTEMPTS, NORMAL_ATTEMPTS + EXTENSION_ATTEMPTS):
            try:
                return _run_prolog_attempt(generate_fn, i, question, retrieved_context, error_history, last_attempt_tracker[0], last_attempt_tracker, question_type)
            except Exception as e:
                _handle_attempt_error(e, i, "Extension")
        _logger.warning("Extension attempts also exhausted.")
    else:
        _logger.info("LLM says NO (or check failed) — skipping extension.")

    raise Exception("Failed to generate valid Prolog code after multiple attempts.")


