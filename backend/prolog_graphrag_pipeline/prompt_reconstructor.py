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
    elif not explainer_output:
        logical_evidence_text = ""

    # ── Assemble sections ────────────────────────────────────────────────
    sections = []
    sections.append(f"USER QUESTION:\n{question}")

    if flag != "q" and retrieved_context:
        sections.append(f"RETRIEVED KNOWLEDGE:\n{retrieved_context}")

    if flag != "q" and logical_evidence_text:
        sections.append(f"LOGICAL EVIDENCE:\n{logical_evidence_text}")

    if flag == "x" and conclusion != "See Logical Evidence":
        sections.append(f"CONCLUSION: {conclusion}")

    body = "\n\n".join(sections)

    return f"""### FINAL SYNTHESIS TASK

{body}
"""


if __name__ == "__main__":
    print(reconstruct_prompt(question="QUESTION", retrieved_context="CONTEXT", explainer_output="", flag="q"), "\n")
    print(reconstruct_prompt(question="QUESTION", retrieved_context="CONTEXT", explainer_output="", flag=r"x\c"), "\n")
    print(reconstruct_prompt(question="QUESTION", retrieved_context="CONTEXT", explainer_output="", flag="x"), "\n")