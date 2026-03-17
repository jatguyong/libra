"""Semantic entropy calculation for hallucination detection.

Clusters multiple LLM responses by bidirectional entailment, then
computes entropy over the cluster distribution. High entropy → likely hallucination.
"""

import json
import math
import logging
from typing import Optional

from .llm_config import MODEL_NAME, get_openai_client

logger = logging.getLogger(__name__)

OPTIMAL_SE_THRESHOLD = 0.3316

client = get_openai_client()

NLI_SYSTEM_PROMPT = [
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


def query_llm(prompt: str) -> Optional[str]:
    """Send a prompt to the NLI judge and return the JSON response text."""
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=NLI_SYSTEM_PROMPT + [{"role": "user", "content": prompt}],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content


def check_entailment(seq1: str, seq2: str) -> bool:
    """Check bidirectional entailment between two LLM responses."""
    prompt = f"""
Given the following two responses to the same question, determine if they are semantically equivalent.

Response 1: {seq1}

Response 2: {seq2}
    """
    try:
        answer = query_llm(prompt)
        if not answer:
            return False
            
        t = answer.strip()
        if "```json" in t:
            t = t.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in t:
            t = t.split("```", 1)[1].split("```", 1)[0].strip()
            
        start = t.find('{')
        end = t.rfind('}')
        if start != -1 and end != -1:
            t = t[start:end+1]
            
        answer_dict = json.loads(t)
        verdict = answer_dict.get("verdict", "").lower()
        return verdict == "yes"
    except Exception as e:
        logger.error(f"Entailment check failed or JSON decode error. Returning False. Error: {e}")
        return False


def cluster_sequences(sequences: list[dict]) -> list[list[dict]]:
    """Group sequences into clusters where members are semantically equivalent."""
    logger.debug("Clustering %d sequences...", len(sequences))
    C = [[sequences[0]]]
    for m in range(1, len(sequences)):
        assigned = False
        for c in C:
            if check_entailment(c[0]["text_answer"], sequences[m]["text_answer"]):
                assigned = True
                c.append(sequences[m])
                break
        if not assigned:
            C.append([sequences[m]])
    return C


def compute_aggregated_logprobs(response: dict) -> float:
    """Sum logprobs for a single response and convert to probability."""
    if not response.get("logprobs"):
        return 1.0

    sequence_probability = 0
    for token_logprob in response["logprobs"]:
        if hasattr(token_logprob, "logprob"):
            sequence_probability += token_logprob.logprob
        elif isinstance(token_logprob, dict):
            sequence_probability += token_logprob.get("logprob", 0)
        elif isinstance(token_logprob, (float, int)):
            sequence_probability += token_logprob

    return math.e ** sequence_probability


def compute_semantic_entropy(sequences_input: dict) -> dict:
    """Compute semantic entropy over clustered LLM responses.

    Args:
        sequences_input: {"sequences": [str, ...], "logprobs": [[...], ...]}

    Returns:
        {"best_answer": dict, "semantic_entropy": float, "hallucination_flag": str}
    """
    sequences_str = sequences_input["sequences"]
    logprobs_list = sequences_input["logprobs"]

    sequences = [
        {"text_answer": seq, "logprobs": logprobs}
        for seq, logprobs in zip(sequences_str, logprobs_list)
    ]

    clusters = cluster_sequences(sequences)

    total_sequences = len(sequences)
    semantic_entropy = 0
    highest_probability = 0
    highest_probability_cluster = None

    for cluster in clusters:
        p_Ci_x = len(cluster) / total_sequences
        if p_Ci_x > highest_probability:
            highest_probability = p_Ci_x
            highest_probability_cluster = cluster
        semantic_entropy += p_Ci_x * math.log(p_Ci_x)

    semantic_entropy *= -1
    representative_sequence = highest_probability_cluster[0]

    return {
        "best_answer": representative_sequence,
        "semantic_entropy": semantic_entropy,
        "hallucination_flag": "likely_hallucination" if semantic_entropy > OPTIMAL_SE_THRESHOLD else "likely_correct",
    }