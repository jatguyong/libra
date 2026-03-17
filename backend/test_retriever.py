import sys
import logging
logging.basicConfig(level=logging.DEBUG)

from prolog_graphrag_pipeline.graphrag.neo4j_manager import get_driver
from prolog_graphrag_pipeline.graphrag.llm_wrapper import initialize_models
from prolog_graphrag_pipeline.graphrag.kbpedia_retriever import KBPediaRetriever

def main():
    driver = get_driver()
    _, retriever_llm, embedder = initialize_models()
    
    retriever = KBPediaRetriever(driver=driver, llm=retriever_llm, top_k=5, embedder=embedder)
    
    q = "What are the exact steps or concepts related to photosynthesis?"
    
    print("\n=== EXTRACTING ENTITIES ===")
    ents = retriever.extract_entities(q)
    print(ents)
    
    print("\n=== SEARCHING ===")
    res = retriever.search(q, top_k=5, original_query=q)
    
    print(f"\nFound {len(res.items)} items")
    for item in res.items:
        print(f"Entity: {item.metadata.get('entity')}")
        print(f"Triples: {item.metadata.get('triples')}")
        print("---")

if __name__ == "__main__":
    main()
