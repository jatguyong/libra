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
Your job is to translate the "s(CASP) HUMAN-READABLE EXPLANATION" into a highly detailed, clear, and concise LLM-friendly natural-language narrative.

STRICT RULES:
1. **DO NOT MENTION THE SOLVER/SYSTEM**: Write your explanation as truths and not something derived from the solver or system.
2. **NO EXTERNAL KNOWLEDGE:** You must base your explanation *entirely* on the provided s(CASP) explanation and context. Do not inject outside facts.
3. **DO NOT CONTRADICT THE PROOF:** The s(CASP) output is the absolute ground truth. Whatever answer it arrives at is correct, even if you disagree. DO NOT output a different answer than what the logic proved.
4. **BE EXPLANATORY BUT CONCISE:** Walk through the logical steps the solver took in informative detail, not bloat. Explain the context, the relevant rules that were applied, the connections made between entities, and exactly *how* they collectively lead to the final conclusion.
5. **TRANSLATE PROLOG CODE INTO NATURAL LANGUAGE:** Translate Prolog code statements, variables, and rules into rich, human-readable language like you are generating an answer, not simply evaluating code. For instance, rather than saying "The system evaluated same_conditions(X, Y)", say "The solver applies the 'same_conditions' rule, which links the two gases, carbon dioxide and ammonia, based on their identical conditions." Transform the mechanical proof into a comprehensible narrative.
6. **NO PROLOG JARGON:** Do not use words like "s(CASP)", "Prolog", "holds for", "justification tree", or "predicate". Write naturally as if explaining a logical roadmap.
"""
    return prompt

def generate_explanation(question: str, retrieved_context: str, database: str, query: str, retrieved_values: str, human_readable_explanation: str) -> str:
    from .prolog_llms import generate
    explanation = generate(prompt=generate_explanation_prompt(question=question, retrieved_context=retrieved_context, database=database, query=query, retrieved_values=retrieved_values, human_readable_explanation=human_readable_explanation), flag="explanation")
    if explanation:
        return explanation['text_answer']
    return None