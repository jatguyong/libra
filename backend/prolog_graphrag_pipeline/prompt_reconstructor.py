import re
from typing import Optional

def capture_conclusion_and_logical_path(explainer_output):
    pattern = r"\*\*(?:Conclusion|CONCLUSION):\*\*\s*(.*)"
    match = re.search(pattern, explainer_output)
    if match:
        conclusion = match.group(1).strip()
        logical_evidence = explainer_output[match.end():].strip()
    else:
        conclusion = "Not extracted. Refer to logical evidence."
        logical_evidence = explainer_output
    return conclusion, logical_evidence

def reconstruct_prompt(question: str, retrieved_context: str, explainer_output: str, flag: str):
    conclusion = "See Logical Evidence"
    logical_evidence_text = explainer_output
    
    # The regex pattern
    pattern = r"\*\*Conclusion:\*\*\s*(.*?)(?=\n\s*\*\*|$)"

    # Search using re.DOTALL so '.' matches newlines as well
    match = re.search(pattern, explainer_output, flags=re.DOTALL)

    if match:
        # Extract the first capture group and strip any trailing whitespace
        conclusion_snippet = match.group(1).strip()
        conclusion = conclusion_snippet
        logical_evidence_text = explainer_output.replace(conclusion, "")
        # print(conclusion_snippet)
    else:
        logical_evidence_text = "No logical evidence available. Use your knowledge and the retrieved context to answer."
        print("Conclusion not found.")

    # Determine if Prolog generated verified evidence or if we are falling back
    prolog_verified = bool(explainer_output and explainer_output.strip() and
                           explainer_output.strip() != "No logical evidence available.")

    # Combine user-provided context (from prompt) with retrieved context
    full_context = ""
    if retrieved_context:
        full_context += f"RETRIEVED KNOWLEDGE:\n{retrieved_context}"

    context_part = f"CONTEXT:\n{full_context}" if flag != r"q" else ""
    conclusion_part = f"CONCLUSION: {conclusion}" if flag == r"x" else ""
    logical_evidence_part = f"LOGICAL EVIDENCE: {logical_evidence_text}" if flag != r"q" else ""

    # Build authority instruction based on what evidence is available
    if prolog_verified:
        authority_instruction = """
### CRITICAL ENFORCEMENT
The PROLOG-VERIFIED LOGICAL EVIDENCE above is the output of a formal logic engine.
You MUST base your answer letter DIRECTLY on this evidence.
DO NOT override it. DO NOT say "None" or "None of the above".
"""
    else:
        authority_instruction = ""

    return f"""### FINAL SYNTHESIS TASK

USER QUESTION:
{question}

{conclusion_part}

{logical_evidence_part}

    """
# {authority_instruction}
# Your response MUST begin with EXACTLY this phrase on the very first line:
# "Based on my synthesis of knowledge, the answer is [Letter]. [Exact choice text]."

# Where [Letter] is ONE of: A, B, C, or D — matching EXACTLY the letter label in the question.
# Where [Exact choice text] is the VERBATIM text of that choice from the question.

if __name__ == "__main__":
    print(reconstruct_prompt(question="QUESTION", retrieved_context="CONTEXT", explainer_output="", flag="q"), "\n")
    print(reconstruct_prompt(question="QUESTION", retrieved_context="CONTEXT", explainer_output="", flag=r"x\c"), "\n")
    print(reconstruct_prompt(question="QUESTION", retrieved_context="CONTEXT", explainer_output="", flag="x"), "\n")