OPTIMAL_SE_THRESHOLD = 0.3316

import json
from config import ENTAILMENT_THRESHOLD, SampleSequencesFlags, CORRECTNESS_THRESHOLD
from . import main_driver

import math
import csv
import sys
import json
import os
from pathlib import Path
from typing import Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))
IO_DIR = ROOT / "explainability_evaluation_results/data"
TEST_DIR = ROOT / "test_cases"
LOGS_DIR = ROOT / "logs/prolog_graphrag_pipeline_logs"

# Ensure project root is on the path so llm_config can be imported
# _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# if _project_root not in sys.path:
#     sys.path.insert(0, _project_root)

from .llm_config import MODEL_NAME, get_openai_client

from openai import OpenAI

# For OpenAI
client = OpenAI()

# ── System Prompt ────────────────────────────────────────────────────────────
LLM_MESSAGES = [
    {
        "role": "system",
        "content": """\
### ROLE:
You are an expert Logical Analyst specialized in symbolic reasoning and Natural Language Inference (NLI).

### TASK:
Determine if two LLM responses, generated from a structured logic pipeline, are "Semantically Equivalent" using Bidirectional Entailment. You must specifically evaluate both the final conclusion AND the step-by-step explanation (reasoning trace), if present.

### DEFINITION OF EQUIVALENCE (Bidirectional Entailment):
    - Two responses are equivalent ONLY if they logically entail one another in both their conclusions and their supporting explanations. This means:
    - Direction A to B (Explanation & Conclusion): The core facts, logical reasoning steps, and final conclusion of Response A logically support and encompass the core meaning of Response B's explanation and conclusion.
    - Direction B to A (Explanation & Conclusion): The core facts, logical reasoning steps, and final conclusion of Response B logically support and encompass the core meaning of Response A's explanation and conclusion.
    - The Final Answer: Both responses must arrive at the exact same final conclusion or verdict.

### TOLERANCE CRITERIA:
    - Deductive Variations: Differences in how explicitly the deductive steps are narrated do NOT break equivalence, provided the underlying logic remains sound and identical.
    - Stylistic Differences: Variations in phrasing, verbosity, sentence order, or the inclusion of minor, non-contradictory conversational filler do NOT constitute a difference in meaning.

### REJECTION CRITERIA (Verdict: "no"):
Reject equivalence immediately if ANY of the following apply:
    - Contradiction: One response contains a factual or logical contradiction to the other in either the explanation or the conclusion.
    - Unidirectional Meaning (Explanation): One response's explanation introduces a major, pivotal claim, premise, or logical step that is entirely absent from the other, breaking the two-way entailment.
    - Conclusion Mismatch: The final answers differ in any way (e.g., "True" vs. "Unknown", or mutually exclusive categorical answers).

### JSON SCHEMA:
{
"rationale": "A concise explanation of the bidirectional entailment check, noting specifically why the explanations and conclusions match or fail to match.",
"verdict": "yes" | "no"
}
""",
    }
]


# ── Unified Generation Function ─────────────────────────────────────────────
def query_llm(prompt: str):
    """Send a prompt to the configured LLM and return the response text."""
    # try:
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=LLM_MESSAGES + [{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return response.choices[0].message.content
    # except Exception as e:
    #     print(f"Error during LLM interaction ({MODEL_NAME}): {e}")
    #     return None


def sample_sequences(prompt: str) -> dict:
    response = main_driver.run_pipeline(question=prompt, flag="x", sample_mode=True)
    return response


def check_entailment(seq1: str, seq2: str) -> bool:
    prompt = f"""
Given the following two responses to the same question, determine if they are semantically equivalent.

Response 1: {seq1}

Response 2: {seq2}
    """
    
    answer = query_llm(prompt)
    # print(answer)
    answer_dict = json.loads(answer)
    verdict = answer_dict.get("verdict", "").lower()
    return verdict.lower() == "yes"


def cluster_sequences(sequences: list[dict]) -> list[list[dict]]:
    print(f"    Clustering sequences...")
    C = [[sequences[0]]]
    M = 5
    for m in range(1, M):
        assigned = False
        for c in C:
            first_seq = c[0]["text_answer"]
            entailment = check_entailment(first_seq, sequences[m]["text_answer"])
            if entailment:
                assigned = True
                c.append(sequences[m])
                break
        if not assigned:
            C.append([sequences[m]])
    return C


def compute_likelihood(cluster: list[dict]) -> float:
    likelihood = 0
    for seq in cluster:
        # print(f"Here's a SEQUENCE: {seq}")
        likelihood += compute_aggregated_logprobs(seq)
    return likelihood


def compute_aggregated_logprobs(response: dict) -> float:
    sequence_probability = 0
    for token_logprob in response["logprobs"]:
        sequence_probability += token_logprob
        
    sequence_probability = math.e ** sequence_probability
    return sequence_probability
    

def compute_semantic_entropy(sequences):
    sequences_str = sequences["sequences"]
    logprobs_list = sequences["logprobs"]

    sequences = []
    for seq, logprobs in zip(sequences_str, logprobs_list):
        sequences.append(
            {
                "text_answer": seq,
                "logprobs": logprobs, 
            }
        )
    
    clusters = cluster_sequences(sequences)
    sum_of_cluster_probabilities = sum(compute_likelihood(cluster) for cluster in clusters)
    semantic_entropy = 0
        
    highest_probability_cluster = None
    highest_probability = 0
    for cluster in clusters:
        p_Ci_x = compute_likelihood(cluster) / sum_of_cluster_probabilities
        if p_Ci_x > highest_probability:
            highest_probability = p_Ci_x
            highest_probability_cluster = cluster
        semantic_entropy += p_Ci_x * math.log(p_Ci_x)
            
    representative_sequence = highest_probability_cluster[0]
    semantic_entropy *= -1
    
    return {
        "best_answer": representative_sequence,
        "semantic_entropy": semantic_entropy,
        "hallucination_flag": "likely_hallucination" if semantic_entropy < OPTIMAL_SE_THRESHOLD else "likely_correct"
    }
    
    