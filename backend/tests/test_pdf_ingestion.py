"""
PDF Ingestion Benchmark Test
=============================
Tests the full PDF ingestion pipeline:
1. Initializes GraphRAG pipeline (Neo4j + LLM + embedder)
2. Ingests a sample PDF into Neo4j via SimpleKGPipeline
3. Verifies Document and Chunk nodes exist
4. Measures execution time
5. Tests per-document removal
6. Verifies other nodes are unaffected

Usage:
    cd c:\\Users\\John Reniel\\libra-1\\backend
    python -m tests.test_pdf_ingestion
    
Requirements:
    - Neo4j running at neo4j://127.0.0.1:7687
    - TOGETHER_API_KEY environment variable set  
    - At least one PDF in backend/uploads/
"""

import os
import sys
import time

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))


def test_ingestion():
    from prolog_graphrag_pipeline.graphrag import graphrag_driver as gd
    
    # Find test PDF
    uploads_dir = os.path.join(os.path.dirname(__file__), "..", "uploads")
    pdf_files = [f for f in os.listdir(uploads_dir) if f.endswith(".pdf")] if os.path.isdir(uploads_dir) else []
    
    if not pdf_files:
        print("ERROR: No PDF files found in backend/uploads/. Please add at least one PDF.")
        return
    
    test_pdf = os.path.join(uploads_dir, pdf_files[0])
    print(f"{'='*60}")
    print(f"PDF INGESTION BENCHMARK TEST")
    print(f"{'='*60}")
    print(f"Test file: {test_pdf}")
    print(f"File size: {os.path.getsize(test_pdf) / 1024:.1f} KB")
    print()
    
    # Step 1: Initialize pipeline
    print("[1/5] Initializing GraphRAG pipeline...")
    start = time.perf_counter()
    gd.init_globals()
    init_duration = time.perf_counter() - start
    print(f"      Pipeline initialized in {init_duration:.2f}s")
    print()
    
    # Step 2: Count existing nodes (to verify we don't damage them later)
    print("[2/5] Counting existing Neo4j nodes...")
    gd.ensure_driver_connected()
    with gd.neo4j_driver.session(database="neo4j") as session:
        pre_count = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
        pre_kbpedia = session.run("MATCH (n:KBPediaConcept) RETURN count(n) as c").single()["c"]
    print(f"      Total nodes before ingestion: {pre_count}")
    print(f"      KBPedia nodes: {pre_kbpedia}")
    print()
    
    # Step 3: Ingest PDF
    print(f"[3/5] Ingesting PDF: {os.path.basename(test_pdf)}")
    overall_start = time.perf_counter()
    results = gd.ingest_pdf_files([test_pdf])
    overall_duration = time.perf_counter() - overall_start
    
    print(f"\n      INGESTION RESULTS:")
    for r in results:
        print(f"        File: {os.path.basename(r['file'])}")
        print(f"        Status: {r['status']}")
        print(f"        Duration: {r['duration_s']}s")
        if 'error' in r and r['error']:
            print(f"        Error: {r['error']}")
    print(f"\n      Total ingestion time: {overall_duration:.2f}s")
    print()
    
    # Step 4: Verify nodes exist
    print("[4/5] Verifying Neo4j nodes...")
    docs = gd.list_ingested_documents()
    print(f"      Ingested documents in Neo4j: {len(docs)}")
    for doc in docs:
        print(f"        - {doc['path']} ({doc['chunk_count']} chunks)")
    
    with gd.neo4j_driver.session(database="neo4j") as session:
        post_count = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
        post_kbpedia = session.run("MATCH (n:KBPediaConcept) RETURN count(n) as c").single()["c"]
        doc_count = session.run("MATCH (d:Document) RETURN count(d) as c").single()["c"]
        chunk_count = session.run("MATCH (c:Chunk) RETURN count(c) as c").single()["c"]
    
    new_nodes = post_count - pre_count
    print(f"\n      Total nodes after ingestion: {post_count} (+{new_nodes} new)")
    print(f"      Document nodes: {doc_count}")
    print(f"      Chunk nodes: {chunk_count}")
    print(f"      KBPedia nodes: {post_kbpedia} (should be unchanged)")
    assert post_kbpedia == pre_kbpedia, "KBPedia nodes were modified!"
    print()
    
    # Step 5: Test removal
    test_filename = os.path.basename(test_pdf)
    print(f"[5/5] Testing removal of '{test_filename}'...")
    removal_start = time.perf_counter()
    removal_result = gd.remove_document_from_kg(test_filename)
    removal_duration = time.perf_counter() - removal_start
    
    print(f"      Removal result: {removal_result}")
    print(f"      Removal duration: {removal_duration:.2f}s")
    
    with gd.neo4j_driver.session(database="neo4j") as session:
        final_count = session.run("MATCH (n) RETURN count(n) as c").single()["c"]
        final_kbpedia = session.run("MATCH (n:KBPediaConcept) RETURN count(n) as c").single()["c"]
    
    print(f"\n      Total nodes after removal: {final_count}")
    print(f"      KBPedia nodes after removal: {final_kbpedia} (should still be unchanged)")
    assert final_kbpedia == pre_kbpedia, "KBPedia nodes were modified during removal!"
    
    print()
    print(f"{'='*60}")
    print(f"BENCHMARK SUMMARY")
    print(f"{'='*60}")
    print(f"  PDF file:          {test_filename}")
    print(f"  File size:         {os.path.getsize(test_pdf) / 1024:.1f} KB")
    print(f"  Init time:         {init_duration:.2f}s")
    print(f"  Ingestion time:    {overall_duration:.2f}s")
    print(f"  Chunks created:    {chunk_count}")
    print(f"  Nodes created:     {new_nodes}")
    print(f"  Removal time:      {removal_duration:.2f}s")
    print(f"  KBPedia preserved: {'YES' if final_kbpedia == pre_kbpedia else 'NO!'}")
    print(f"{'='*60}")


if __name__ == "__main__":
    test_ingestion()

