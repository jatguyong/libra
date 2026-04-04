import sys
import os
import json
sys.path.append(os.path.abspath('backend/prolog_graphrag_pipeline'))

from dotenv import load_dotenv
load_dotenv()

from graphrag.kbpedia_retriever import KBPediaRetriever
kr = KBPediaRetriever()

candidates = [{"name": f"Concept {i}", "definition": f"Def {i}"} for i in range(24)]

try:
    res = kr._filter_concepts_once("rotating body", candidates)
    print("KEPT INDICES COUNT:", len(res))
    for c in res:
        print(c["name"])
except Exception as e:
    print("FAILED", e)
