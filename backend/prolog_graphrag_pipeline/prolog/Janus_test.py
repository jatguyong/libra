# import ollama

# print("Asking Ollama (with confidence scores)...")
# response = ollama.chat(
#     model='llama3:instruct',
#     messages=[
#         {'role': 'user', 'content': 'Who are you?'}
#     ],
#     options={
#         'temperature': 0  
#     },
#     logprobs=True     
# )

# print(f"Answer: {response['message']['content']}\n")

# if 'logprobs' in response:
#     print("--- Confidence Scores (First 5 Tokens) ---")
#     for token_data in response['logprobs'][:5]:
#         token_str = token_data.get('token', '')
#         score = token_data.get('logprob', -999) 
        
#         # A score close to 0 (e.g., -0.01) is VERY confident.
#         # A score like -2.5 is LOW confidence.
#         print(f"Token: '{token_str}' | Logprob: {score:.4f}")
# else:
#     print("Logprobs not found. Ensure your Ollama server version is up to date.")

import janus_swi as janus

list(janus.query("pack_install(scasp, [interactive(false)])."))
list(janus.query("use_module(library(scasp/human))."))
janus.query_once("use_module(library(scasp/human)).")

# 2. Use consult("user", ...) for multi-line strings
logic = r"""
ceo(apex_corp, mark).
sibling(mark, steven).
parent(steven, leo).
guardian(steven, leo).

uncle(Uncle, Nephew) :- 
    parent(Parent, Nephew), 
    sibling(Uncle, Parent).
    
explain_uncle_safe(Person, Uncle, TreeStr) :-
    scasp(uncle(Uncle, Person), [tree(RawTree)]),
    term_string(RawTree, TreeStr).
    
explain_uncle(Uncle, Nephew, TreeStr) :-
    % We call the original predicate with the same arguments
    scasp(uncle(Uncle, Nephew), [tree(RawTree)]),
    % Shield the raw tree by converting it to a string
    term_string(RawTree, TreeStr).
"""
janus.consult("user", logic)

# 3. THE FIX: We use a semicolon to separate the 'raw' tree from the result
# and we use term_string to make a version Python can read.
# We ask Janus for 'Uncle' and 'TreeStr' specifically.
query = """
explain_uncle_safe(leo, Uncle, TreeStr)
"""

try:
    # Use query_once. It returns a dictionary.
    result = janus.query_once(query)
    
    if result:
        print(f"Success! Uncle: {result['Uncle']}")
        print("\n--- Justification Tree (Text) ---")
        # Python can read 'TreeStr' because it's just a string!
        print(result['TreeStr'])
    else:
        print(" No solution found.")
        
except Exception as e:
    print(f"🔥 Error: {e}")
    