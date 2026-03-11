import janus_swi as janus

def generate_explanation_prompt(question: str, retrieved_context: str, retrieved_values: str) -> str:
    prompt = f"""
Your Prolog database has been successfully generated and consulted. Now, provide a detailed, logical, and step-by-step human-readable explanation of the justification Prolog gave. It should serve as context for answering the user's question.
User Question:
{question}

Context:
{retrieved_context}

The values retrieved from the query are:
{retrieved_values}
"""

    return prompt

def generate_safe_scasp_wrapper(query):
    query = query.replace(".", "").replace("\n", "")
    return rf"""
explain(Explanation) :-
    % 1. Run the solver - wrap query in parenthesis so commas are not evaluated as separate arguments
    scasp(({query}), [tree(Tree)]),
    
    % 2. Capture the human-readable output into a string
    with_output_to(string(Explanation), 
        human_justification_tree(Tree, [tree_style(human)])
    ).
"""

def generate_explanation_prompt(question: str, retrieved_context: str, database: str, query: str, human_readable_explanation: str, retrieved_values: str) -> str:
    prompt = f"""
### DECODER TASK: ELUCIDATE LOGICAL PROOF
**USER QUESTION:**
{question}

**RETRIEVED CONTEXT:**
{retrieved_context}

**DATABASE:**
{database}
        
**QUERY**:
{query}

**RETRIEVED VALUES**:
{retrieved_values} 

**s(CASP) HUMAN-READABLE EXPLANATION:**
{human_readable_explanation}

### INSTRUCTION:
Your ONLY job is to translate the "s(CASP) HUMAN-READABLE EXPLANATION" into a clear, natural-language narrative.

STRICT RULES:
1. **NO EXTERNAL KNOWLEDGE:** You must base your explanation *entirely* on the provided s(CASP) explanation and context. Do not inject outside facts.
2. **DO NOT CONTRADICT THE PROOF:** The s(CASP) output is the absolute ground truth. Whatever answer it arrives at is correct, even if you disagree. DO NOT output a different answer than what the logic proved.
3. **EXPLAIN THE "WHY":** Walk through the logical steps the solver took (e.g. "Because X holds, and Y also holds, the system concluded Z").
4. **NO PROLOG JARGON:** Do not use words like "s(CASP)", "Prolog", "holds for", or "justification tree". Write naturally.
"""
    return prompt

def generate_explanation(question: str, retrieved_context: str, database: str, query: str, retrieved_values: str, human_readable_explanation: str) -> str:
    try:
        from .prolog_llms import generate
    except ImportError:
        from .prolog_llms import generate
    explanation = generate(prompt=generate_explanation_prompt(question=question, retrieved_context=retrieved_context, database=database, query=query, retrieved_values=retrieved_values, human_readable_explanation=human_readable_explanation), flag="explanation")
    if explanation:
        return explanation['text_answer']
    return None