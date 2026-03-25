import logging
import os
import sys
import subprocess
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://neo4j:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "graphrag")

def main():
    print("Checking KBPedia in Neo4j...", flush=True)
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
        with driver.session(database="neo4j") as session:
            res = session.run("MATCH (n:KBPediaConcept) RETURN count(n) as c")
            count = res.single()["c"]
        driver.close()
        
        if count == 0:
            print("KBPediaConcepts empty. Running KBPedia loader...", flush=True)
            subprocess.run([sys.executable, "-m", "prolog_graphrag_pipeline.graphrag.kbpedia_loader"], check=True)
            print("KBPedia load complete.", flush=True)
        else:
            logger.info(f"KBPedia already loaded. Found {count} concepts.")
            
    except Exception as e:
        logger.info(f"Error checking KBPedia status: {e}")

if __name__ == "__main__":
    main()
