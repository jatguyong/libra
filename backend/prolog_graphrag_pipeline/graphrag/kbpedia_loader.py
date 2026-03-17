"""
KBPedia N3 → Neo4j Loader
Parses the KBPedia reference concepts N3 file and loads owl:Class entries
into Neo4j as :KBPediaConcept nodes with SUBCLASS_OF relationships.

Usage:
    python -m prolog_graphrag_pipeline.graphrag.kbpedia_loader
"""

import sys
import time
from pathlib import Path
from neo4j import GraphDatabase

from .config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

# Try multiple locations for the N3 file
_candidates = [
    Path(__file__).resolve().parents[2] / "kbpedia_reference_concepts_linkage.n3",
    Path(__file__).resolve().parents[3] / "neo4j_kbpedia" / "kbpedia_reference_concepts_linkage.n3",
]
N3_FILE = next((p for p in _candidates if p.exists()), _candidates[0])

BATCH_SIZE = 500


import re

def parse_n3(filepath: Path):
    """
    Parse the N3 file iteratively without rdflib to prevent OOM errors on 10.5MB+ files.
    Extracts class data and Wikidata Q-ID mappings.
    """
    print(f"Iteratively parsing N3 file: {filepath} (this may take a minute)...")
    start = time.time()

    concepts = {}        # uri -> {uri, name, definition, altLabels, wikidata_qid}
    subclass_edges = []  # (child_uri, parent_uri)
    
    current_concept = None

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('@') or line.startswith('#'):
                continue
                
            # If the line starts with a colon, it's a new subject block (e.g. :Person a owl:Class)
            if line.startswith(':'):
                match = re.search(r'^:([A-Za-z0-9_-]+)\s+a\s+owl:Class', line)
                if match:
                    current_uri = "http://kbpedia.org/kko/rc/" + match.group(1)
                    current_concept = {
                        "uri": current_uri,
                        "name": match.group(1).replace("-", " "),
                        "definition": "",
                        "altLabels": [],
                        "wikidata_qid": None
                    }
                    concepts[current_uri] = current_concept
                else:
                    # Not an owl:Class, skip reading properties for this block
                    current_concept = None
            
            # If we don't have an active subject block, skip property extraction
            if not current_concept:
                continue
                
            # Extract standard properties
            if "skos:prefLabel" in line:
                m = re.search(r'skos:prefLabel\s+"([^"]+)"', line)
                if m: current_concept["name"] = m.group(1)
                
            if "skos:definition" in line:
                m = re.search(r'skos:definition\s+"([^"]+)"', line)
                if m: current_concept["definition"] = m.group(1)
                
            if "skos:altLabel" in line:
                m = re.search(r'skos:altLabel\s+"([^"]+)"', line)
                if m:
                    for part in m.group(1).split("||"):
                        if part.strip(): current_concept["altLabels"].append(part.strip())
                        
            if "rdfs:subClassOf" in line:
                m = re.search(r'rdfs:subClassOf\s+:([A-Za-z0-9_-]+)', line)
                if m:
                    parent_uri = "http://kbpedia.org/kko/rc/" + m.group(1)
                    subclass_edges.append((current_concept["uri"], parent_uri))
                    
            # Look for Wikidata Q-ID anywhere in the line for this concept
            # Wikidata IDs are usually enclosed in parentheses or pipes, e.g. (Q42) or ||Q42
            if not current_concept["wikidata_qid"]:
                qid_m = re.search(r'\b(Q[1-9]\d*)\b', line)
                if qid_m:
                    current_concept["wikidata_qid"] = qid_m.group(1)


    elapsed = time.time() - start
    print(f"Iteratively parsed {len(concepts)} concepts and {len(subclass_edges)} edges in {elapsed:.1f}s.")
    return concepts, subclass_edges


def load_into_neo4j(concepts: dict, subclass_edges: list):
    """Load concepts and relationships into Neo4j."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    with driver.session(database="neo4j") as session:
        # 1. Create constraint for uniqueness
        print("Creating uniqueness constraint...")
        session.run(
            "CREATE CONSTRAINT kbpedia_uri IF NOT EXISTS "
            "FOR (n:KBPediaConcept) REQUIRE n.uri IS UNIQUE"
        )

        # 2. Batch-create concept nodes
        concept_list = list(concepts.values())
        total = len(concept_list)
        print(f"Loading {total} concepts in batches of {BATCH_SIZE}...")
        
        print("Computing embeddings for KBPedia concepts...")
        try:
            from sentence_transformers import SentenceTransformer
            embedder = SentenceTransformer("all-MiniLM-L6-v2")
            
            # Batch encode
            texts = [f"{c['name']} {c['definition']}" for c in concept_list]
            embeddings = embedder.encode(texts, show_progress_bar=True)
            
            for idx, c in enumerate(concept_list):
                c['embedding'] = embeddings[idx].tolist()
        except ImportError:
            print("WARNING: sentence_transformers not installed. Skipping embeddings.")
            for c in concept_list:
                c['embedding'] = None

        for i in range(0, total, BATCH_SIZE):
            batch = concept_list[i : i + BATCH_SIZE]
            session.run(
                """
                UNWIND $batch AS row
                MERGE (n:KBPediaConcept {uri: row.uri})
                SET n.name = row.name,
                    n.definition = row.definition,
                    n.altLabels = row.altLabels,
                    n.wikidata_qid = row.wikidata_qid,
                    n.embedding = row.embedding
                """,
                batch=batch,
            )
            done = min(i + BATCH_SIZE, total)
            print(f"  [{done}/{total}] concepts loaded.")

        # 3. Batch-create SUBCLASS_OF relationships
        total_edges = len(subclass_edges)
        print(f"Loading {total_edges} SUBCLASS_OF edges...")

        edge_dicts = [{"child": c, "parent": p} for c, p in subclass_edges]
        for i in range(0, total_edges, BATCH_SIZE):
            batch = edge_dicts[i : i + BATCH_SIZE]
            session.run(
                """
                UNWIND $batch AS row
                MATCH (child:KBPediaConcept {uri: row.child})
                MATCH (parent:KBPediaConcept {uri: row.parent})
                MERGE (child)-[:SUBCLASS_OF]->(parent)
                """,
                batch=batch,
            )
            done = min(i + BATCH_SIZE, total_edges)
            print(f"  [{done}/{total_edges}] edges loaded.")

        # 4. Create fulltext index for fast search
        print("Creating fulltext index on KBPediaConcept...")
        session.run(
            """
            CREATE FULLTEXT INDEX kbpediaConceptIndex IF NOT EXISTS
            FOR (n:KBPediaConcept)
            ON EACH [n.name, n.definition]
            """
        )

        # 5. Create vector index for KBPedia
        print("Creating vector index on KBPediaConcept...")
        session.run(
            """
            CREATE VECTOR INDEX kbpediaConceptVectorIndex IF NOT EXISTS
            FOR (n:KBPediaConcept) ON (n.embedding)
            OPTIONS {indexConfig: {
              `vector.dimensions`: 384,
              `vector.similarity_function`: 'cosine'
            }}
            """
        )

    driver.close()
    print("KBPedia loading complete!")


def main():
    if not N3_FILE.exists():
        print(f"ERROR: N3 file not found at {N3_FILE}")
        sys.exit(1)

    concepts, edges = parse_n3(N3_FILE)
    load_into_neo4j(concepts, edges)


if __name__ == "__main__":
    main()
