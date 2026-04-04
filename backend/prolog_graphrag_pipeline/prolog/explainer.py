import janus_swi as janus


def generate_safe_scasp_wrapper(query):
    query = query.replace(".", "").replace("\n", "")
    return rf"""
explain(Explanation) :-
    % 1. Run the s(CASP) solver; capture the proof tree and the model.
    scasp(({query}), [tree(Tree)]),

    % 2. Try the rich human-readable justification tree first.
    %    If human_justification_tree/2 fails (e.g. due to CLP(Q) constraint
    %    nodes that the scasp_just_html:clpq/5 renderer cannot handle), fall
    %    back to a plain-text representation of the raw proof model so that
    %    explain/1 always succeeds and always returns something meaningful.
    (   catch(
            with_output_to(string(Explanation),
                human_justification_tree(Tree, [tree_style(human)])
            ),
            _,        % catch ANY error or failure from the renderer
            fail      % treat caught errors as failure to trigger the fallback
        )
    ->  true          % human-readable succeeded
    ;   % Fallback: serialise the raw proof tree as a readable Prolog term.
        %           format/3 with ~w never throws on any term shape.
        scasp_model(Model),
        format(string(Explanation), "Proof model: ~w~nProof tree: ~w", [Model, Tree])
    ).
"""

def generate_explanation_prompt(question: str, retrieved_context: str, database: str, query: str, human_readable_explanation: str, retrieved_values: str) -> str:
    prompt = f"""### DECODER TASK: ELUCIDATE LOGICAL PROOF

**USER QUESTION:**
{question}

**RETRIEVED CONTEXT:**
{retrieved_context}

**DATABASE:**
{database}

**QUERY:**
{query}

**RETRIEVED VALUES:**
{retrieved_values}

**s(CASP) HUMAN-READABLE EXPLANATION:**
{human_readable_explanation}

### INSTRUCTION:
Your job is to translate the "s(CASP) HUMAN-READABLE EXPLANATION" into a highly detailed, clear, and concise natural-language narrative of the **underlying facts**, NOT the mechanical proof steps.

STRICT RULES:
1. **ABSOLUTE INVISIBILITY RULE**: Do not write about the proof, the solver, the system, or the logic itself. Write purely about the subject matter. 
2. **NO META-LANGUAGE**: BANNED WORDS AND PHRASES include "atomic fact", "conditional rule", "initial condition", "the reasoning shows", "the proof establishes", "the solver applied", "logical path", "based on the rule", "according to the facts".
3. **NO EXTERNAL KNOWLEDGE:** You must base your factual explanation *entirely* on the provided s(CASP) explanation and context. Do not inject outside facts.
4. **BE EXPLANATORY BUT CONCISE:** Walk through the causal sequence and relationships between entities. If event A leads to event B, explain why based on the physics, biology, or context provided, rather than saying "Rule A activates B".
5. **TRANSLATE PROLOG CODE INTO NATURAL LANGUAGE:** Translate Prolog code statements and variables into rich, human-readable facts. For instance, instead of saying "The system evaluated same_conditions(X, Y)", simply state the physical/factual reality: "Carbon dioxide and ammonia exhibit identical pressure and temperature conditions." Transform the mechanical proof into direct, authoritative factual statements.
6. **DO NOT** include snake_case terms in your explanation, transform Prolog code variables, rules, and statements into human-readable language.
7. **NO PROLOG JARGON:** Do not use words like "s(CASP)", "Prolog", "holds for", "justification tree", or "predicate".
"""
    return prompt

def generate_explanation(question: str, retrieved_context: str, database: str, query: str, retrieved_values: str, human_readable_explanation: str) -> str:
    from .prolog_llms import generate
    explanation = generate(prompt=generate_explanation_prompt(question=question, retrieved_context=retrieved_context, database=database, query=query, retrieved_values=retrieved_values, human_readable_explanation=human_readable_explanation), flag="explanation")
    if explanation:
        return explanation['text_answer']
    return None