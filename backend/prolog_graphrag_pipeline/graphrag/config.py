import os
from pathlib import Path
from enum import Enum
from neo4j_graphrag.generation.prompts import RagTemplate

NEO4J_URI = os.environ.get("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USERNAME = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "graphrag")
DB_NAME = "graphrag-kg"
GLOBAL_KB = "KBPEDIA"

# Wikidata Fallback: When KBPedia has no match for an entity,
# fall back to Wikidata REST Search API + structural SPARQL.
ENABLE_WIKIDATA_FALLBACK = True

# Coarse concept-level filtering before triple filtering.
ENABLE_KBPEDIA_CONCEPT_FILTER = True
ENABLE_LLM_FILTERING = True


RETRIEVER = "HybridRetriever"

PROMPT_TEMPLATE = '''
### ROLE: Knowledge Extraction Expert
You are a highly skilled Knowledge Engineer specializing in extracting high-fidelity, logical knowledge graphs from complex scientific, technical, or domain-specific texts. Your primary goal is to map novel, document-specific information while explicitly grounding universal knowledge to standard ontologies.

### INSTRUCTIONS:
1. **Universal Ontology Mapping (`KBPediaConcept`)**: FOR ALL universal classes, scientific theories, natural phenomena, mathematical principles, or broad domain concepts, you **MUST** assign the node label `KBPediaConcept`. Assign them standardized, universally recognized names (e.g., "Law of Gravity" instead of "the gravity rule mentioned earlier"). This acts as an explicit hook that allows the downstream system to dynamically snap and link this node to the global KBPedia Knowledge Base.
2. **Novel & Specific Entities**: For specific, novel, or document-local information (e.g., a specific paper's proposed algorithm, a unique experiment event, a specific researcher, or a precise numeric result), assign the most appropriate specific node label (e.g., `Event`, `ScientificTheory`, `Person`, `Technology`).
3. **Aggressive Synthesis**: Extract dense networks of relationships. Build complex bridges between `KBPediaConcept` nodes (existing classical knowledge) and your novel specific nodes (new information from the text). Capture explicit logical flows (IF-THEN, CAUSE-EFFECT, PART-OF, IS_A).
4. **Schema Adherence**: Use the provided Node Labels and Relationship Types strictly. Do not invent new labels outside the provided contextual schema.
5. **Prolog Compatibility**: Ensure all `id` fields are strictly `lowercase_with_underscores`.
6. **Rich Metadata**: For every relationship, provide a `natural_statement` (full sentence preservation), a `logic_intent` (FACT, RULE, or EXCEPTION), and a `logical_form_hint` (e.g., `causes(friction, heat)`).

### JSON OUTPUT FORMAT:
{{
  "nodes": [
    {{
      "id": "concept_id",
      "label": "NodeLabel",
      "properties": {{"name": "Standardized or Specific Display Name"}}
    }}
  ],
  "relationships": [
    {{
      "type": "REL_TYPE",
      "start_node_id": "id1",
      "end_node_id": "id2",
      "properties": {{
        "natural_statement": "The full sentence explaining this link",
        "logic_intent": "FACT | RULE | EXCEPTION",
        "logical_form_hint": "e.g., occurs_in(X, Y)"
      }}
    }}
  ]
}}

### CONTEXTUAL SCHEMA:
{schema}

### EXTRACTION EXAMPLES:
{examples}

### INPUT TEXT:
{text}

Output ONLY the JSON object. No markdown, no filler.
'''

RETRIEVAL_QUERY = '''
// Part A: Local Document Retrieval (Vector/Keyword matches passed as `node`)
RETURN 
    node.text as text,
    score,
    {
        score: score,
        source: "Local Document",
        id: elementId(node)
    } as metadata
'''

# Additional instructions if ever needed.
# 1. Read the Context carefully.
# 2. Identify which specific sentence supports your answer.
# 3. If the context contains multiple objects or events, do NOT mix them up. 
# 4. If the answer is not in the context, say "I don't know."

GRAPHRAG_TEMPLATE_STR = '''
### ROLE
You are a rigorous Logic Extraction Agent. Your purpose is to extract and structure factual and logical building blocks from the Retrieved Context to evaluate the User Query. These blocks will be used by a strict logical reasoning engine, so absolute precision, deduplication, and adherence to format are required.

### EXTRACTION CATEGORIES
You MUST categorize the extracted knowledge into the following four exact sections. 

**ATOMIC FACTS**: Unconditional, standalone truths extracted directly from the Context for ALL concepts in the query. (e.g., "The cell wall provides mechanical support.")
**CONDITIONAL RULES**: Causal relationships, laws, or theorems explicitly found in the Context. Format these as IF-THEN statements. (e.g., "IF an object has mass, THEN it exerts gravity.")
**EXCEPTIONS**: Explicit boundary conditions, caveats, or exceptions to the rules mentioned in the Context. (e.g., "EXCEPT when the system is in a vacuum.")
**LOGICAL GAPS**: Essential missing premises or bridging facts NOT found in the Context that are strictly necessary to definitively answer the User Query or complete the logical chain.

### STRICT CONSTRAINTS
1. UNBIASED EXTRACTION: Extract information relevant to ALL options or concepts in the User Query. Do not assume an answer prematurely; let the reasoning engine decide.
2. NO META-COMMENTARY: Do not write "Option B is incorrect because..." Just state the facts and rules in isolation.
3. CRITICAL DEDUPLICATION: Merge identical or highly similar statements. Do not repeat the exact same fact in different words.
4. GROUNDING: The first three categories MUST be strictly grounded in the provided Context. Category 4 is the ONLY place you may state external missing requirements.

### FORMAT
Output ONLY the ATOMIC FACTS, CONDITIONAL RULES, EXCEPTIONS, and LOGICAL GAPS with a bulleted list under each. If a section has no entries based on the Context, write "None". Do not include introductory filler or a final conclusion. Follow this answer format:

**ATOMIC FACTS**:
   List of atomic facts
**CONDITIONAL RULES**:
   List of conditional rules
**EXCEPTIONS**:
   List of exceptions
**LOGICAL GAPS**:
   List of logical gaps
   
### Question:
{query_text}

### Context:
{context}

### Answer:
'''


GRAPHRAG_FALLBACK_TEMPLATE_STR = """
### ROLE
You are an expert Educational AI Assistant answering a student's question based ONLY on the provided Context.

### STRICT INSTRUCTIONS
1. **Answer First**: Your response MUST begin with EXACTLY this phrase on the VERY FIRST LINE:
   "Based on my synthesis of knowledge, the answer is [Letter]. [Exact choice text]."
   Where [Letter] is one of A, B, C, D and [Exact choice text] is that choice verbatim.
2. **Ignore Irrelevant Facts**: Only use facts that logically connect to solve the query.
3. **No Hallucinations**: If context fails completely, infer from general knowledge but still use the required format.
4. **No "None of the above"**: Always pick the best matching choice from the options given.
5. After the first line, add a brief 1-2 sentence explanation.

### Question:
{query_text}

### Context:
{context}

### Answer:
"""

GRAPHRAG_TEMPLATE = RagTemplate(template=GRAPHRAG_TEMPLATE_STR, expected_inputs=['query_text', 'context'])
GRAPHRAG_FALLBACK_TEMPLATE = RagTemplate(template=GRAPHRAG_FALLBACK_TEMPLATE_STR, expected_inputs=['query_text', 'context'])

DOC_PATH = Path(__file__).resolve().parents[2] / "uploads"

ENCODER_SYSTEM_PROMPT = '''
### ROLE
You are a Query Pre-processor for a Retrieval System. 
Your goal is to split the user's input into:
1. The Core Question (to be sent to the search engine).
2. The Context (any background facts/premises provided in the prompt).

### STRICT INSTRUCTIONS
- IF MULTIPLE CHOICE (A, B, C, D): You MUST preserve the options VERBATIM in the 'question' field. Do NOT strip them.
- CLEANING: Fix typos but keep the original meaning.
- SEPARATION: 
  - 'question': The actual question asked.
  - 'context': A list of sentences/facts provided as background.
- NULL HANDLING: If no context is provided, return an empty list [].
- OUTPUT FORMAT: Return a valid JSON object.

### TASK
Analyze the user's input and structure it as follows:
{
  "rationale": "Brief explanation",
  "question": "The precise question (including options if present)",
  "context": ["Fact 1", "Fact 2"]
}
'''

ENCODER_FEW_SHOT_EXAMPLES = [
  # Example 1: Standard QA
  {"role": "user", "content": "Alise is a doctor and Bob is a nurse. Can Alise prescribe meds?"},
  {"role": "assistant", "content": '''
{
  "rationale": "Separating background facts about professions from the specific question about prescribing rights.",
  "question": "Can Alise prescribe medications?",
  "context": [
    "Alise is a doctor.",
    "Bob is a nurse."
  ]
}
'''},
  
  # Example 2: Logic Puzzle
  {"role": "user", "content": "Assuming every human is mortal, what happens to Socrates?"},
  {"role": "assistant", "content": '''
{
  "rationale": "Extracting the premise about mortality as context and the specific inquiry about Socrates as the question.",
  "question": "What happens to Socrates?",
  "context": [
    "Every human is mortal."
  ]
}
'''},
  
  # Example 3: Multiple Choice (MMLU Style)
  {"role": "user", "content": "What is the capital of France? A) London B) Paris C) Berlin D) Madrid"},
  {"role": "assistant", "content": '''
{
  "rationale": "This is a multiple choice question. The options must be preserved in the question field.",
  "question": "What is the capital of France? A) London B) Paris C) Berlin D) Madrid",
  "context": []
}
'''}
]