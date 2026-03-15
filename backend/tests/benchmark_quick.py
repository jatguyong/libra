"""Quick benchmark to get clean timing numbers for PDF ingestion."""
import os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

from prolog_graphrag_pipeline.graphrag import graphrag_driver as gd

test_pdf = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads", "Photosynthesis.pdf"))
fsize = os.path.getsize(test_pdf) / 1024
print(f"File: Photosynthesis.pdf ({fsize:.1f} KB)")

# Init
t0 = time.perf_counter()
gd.init_globals()
t1 = time.perf_counter()
print(f"Init: {t1-t0:.2f}s")

# Pre-count
with gd.neo4j_driver.session(database="neo4j") as s:
    pre = s.run("MATCH (n) RETURN count(n) as c").single()["c"]
print(f"Pre-ingestion nodes: {pre}")

# Ingest
t2 = time.perf_counter()
results = gd.ingest_pdf_files([test_pdf])
t3 = time.perf_counter()
ing_time = t3 - t2
print(f"Ingestion time: {ing_time:.2f}s")
for r in results:
    fname = os.path.basename(r["file"])
    print(f"  {fname}: status={r['status']}, duration={r['duration_s']}s")
    if r.get("error"):
        print(f"  Error: {r['error']}")

# Post-count
with gd.neo4j_driver.session(database="neo4j") as s:
    post = s.run("MATCH (n) RETURN count(n) as c").single()["c"]
    docs = s.run("MATCH (d:Document) RETURN count(d) as c").single()["c"]
    chunks = s.run("MATCH (c:Chunk) RETURN count(c) as c").single()["c"]
    kb = s.run("MATCH (n:KBPediaConcept) RETURN count(n) as c").single()["c"]
new_nodes = post - pre
print(f"Post-ingestion: +{new_nodes} nodes (docs={docs}, chunks={chunks}, kb_unchanged={kb})")

# Remove
t4 = time.perf_counter()
rm = gd.remove_document_from_kg("Photosynthesis.pdf")
t5 = time.perf_counter()
rm_time = t5 - t4
print(f"Removal: {rm_time:.2f}s -> {rm}")

# Final
with gd.neo4j_driver.session(database="neo4j") as s:
    final = s.run("MATCH (n) RETURN count(n) as c").single()["c"]
    final_kb = s.run("MATCH (n:KBPediaConcept) RETURN count(n) as c").single()["c"]
print(f"Final: {final} nodes, KB={final_kb} (preserved={final_kb==kb})")
print()
print("=== SUMMARY ===")
print(f"  Init:       {t1-t0:.2f}s")
print(f"  Ingestion:  {ing_time:.2f}s")
print(f"  New nodes:  {new_nodes}")
print(f"  Chunks:     {chunks}")
print(f"  Removal:    {rm_time:.2f}s")
print(f"  KB safe:    {final_kb==kb}")
