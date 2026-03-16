"""Prompt reconstruction for the final synthesis LLM.

Takes the user question, retrieved context, and Prolog explainer output,
then assembles them into the structured prompt template.
"""

import re
from typing import Optional


def reconstruct_prompt(question: str, retrieved_context: str, explainer_output: str, flag: str) -> str:
    conclusion = "See Logical Evidence"
    logical_evidence_text = explainer_output

    pattern = r"\*\*Conclusion:\*\*\s*(.*?)(?=\n\s*\*\*|$)"
    match = re.search(pattern, explainer_output, flags=re.DOTALL)

    if match:
        conclusion = match.group(1).strip()
        logical_evidence_text = explainer_output.replace(conclusion, "")
    else:
        logical_evidence_text = "No logical evidence available. Use your knowledge and the retrieved context to answer."

    full_context = ""
    if retrieved_context:
        full_context += f"RETRIEVED KNOWLEDGE:\n{retrieved_context}"

    context_part = f"CONTEXT:\n{full_context}" if flag != r"q" else ""
    conclusion_part = f"CONCLUSION: {conclusion}" if flag == r"x" else ""
    logical_evidence_part = f"LOGICAL EVIDENCE: {logical_evidence_text}" if flag != r"q" else ""

    return f"""### FINAL SYNTHESIS TASK

USER QUESTION:
{question}

{conclusion_part}

{logical_evidence_part}
"""


if __name__ == "__main__":
    print(reconstruct_prompt(question="QUESTION", retrieved_context="CONTEXT", explainer_output="", flag="q"), "\n")
    print(reconstruct_prompt(question="QUESTION", retrieved_context="CONTEXT", explainer_output="", flag=r"x\c"), "\n")
    print(reconstruct_prompt(question="QUESTION", retrieved_context="CONTEXT", explainer_output="", flag="x"), "\n")