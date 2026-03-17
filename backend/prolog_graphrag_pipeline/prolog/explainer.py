import janus_swi as janus


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
Your job is to translate the "s(CASP) HUMAN-READABLE EXPLANATION" into a highly detailed, clear, and comprehensive natural-language narrative.

STRICT RULES:
1. **NO EXTERNAL KNOWLEDGE:** You must base your explanation *entirely* on the provided s(CASP) explanation and context. Do not inject outside facts.
2. **DO NOT CONTRADICT THE PROOF:** The s(CASP) output is the absolute ground truth. Whatever answer it arrives at is correct, even if you disagree. DO NOT output a different answer than what the logic proved.
3. **BE DETAILED AND EXPLANATORY:** Do not just give a brief summary. Walk through the logical steps the solver took in thorough detail. Explain the context, the relevant rules that were applied, the connections made between entities, and exactly *how* they collectively lead to the final conclusion. Break down complex deductive chains into easy-to-understand storytelling.
4. **TRANSLATE PROLOG CODE INTO NATURAL LANGUAGE:** Translate Prolog code statements, variables, and rules into rich, human-readable language like you are generating an answer, not simply evaluating code. For instance, rather than saying "The system evaluated same_conditions(X, Y)", say "The solver applies the 'same_conditions' rule, which links the two gases, carbon dioxide and ammonia, based on their identical conditions." Transform the mechanical proof into a comprehensible narrative.
5. **NO PROLOG JARGON:** Do not use words like "s(CASP)", "Prolog", "holds for", "justification tree", or "predicate". Write naturally as if explaining a logical roadmap.
"""
    return prompt

def generate_explanation(question: str, retrieved_context: str, database: str, query: str, retrieved_values: str, human_readable_explanation: str) -> str:
    from .prolog_llms import generate
    explanation = generate(prompt=generate_explanation_prompt(question=question, retrieved_context=retrieved_context, database=database, query=query, retrieved_values=retrieved_values, human_readable_explanation=human_readable_explanation), flag="explanation")
    if explanation:
        return explanation['text_answer']
    return None