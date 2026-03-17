"""GraphRAG pipeline orchestration.

Coordinates encoder, retriever, LLM, and Neo4j components to answer questions
via knowledge graph construction and retrieval-augmented generation.
"""

import asyncio
import time
import logging

from neo4j_graphrag.experimental.components.text_splitters.fixed_size_splitter import FixedSizeSplitter
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.generation import GraphRAG

from .encoder import process_pdf_documents, process_text_context, process_context, extract_query_and_context
from .retriever import generate, create_retriever
from .config import GRAPHRAG_TEMPLATE, GRAPHRAG_FALLBACK_TEMPLATE, PROMPT_TEMPLATE, SCHEMA_CONFIG, STATIC_SCHEMA
from .neo4j_manager import ensure_driver_connected, get_driver
from .llm_wrapper import initialize_models

logger = logging.getLogger(__name__)

# Persistent event loop to avoid "RuntimeError: Event loop is closed" on Windows.
# asyncio.run() creates and destroys a new loop each call, but httpx/httpcore
# transport cleanup callbacks fire AFTER the loop is closed, causing a crash.
# By reusing a single loop, we keep it alive for the entire process lifetime.
_persistent_loop = None


def _run_async(coro):
    """Run an async coroutine using a persistent event loop (avoids httpx cleanup crash)."""
    global _persistent_loop
    if _persistent_loop is None or _persistent_loop.is_closed():
        _persistent_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_persistent_loop)
    return _persistent_loop.run_until_complete(coro)


# -- KG Pipeline setup --------------------------------------------------------

def setup_kg_pipeline(llm, embedder) -> SimpleKGPipeline:
    """Build the SimpleKGPipeline instances for PDF and text ingestion."""
    neo4j_driver = get_driver()

    STATIC_SCHEMA_DEF = {
        "node_types": [
            "KBPediaConcept",
            "NaturalProcess",
            "ScientificTheory",
            "Organism",
            "Substance",
            "Person",
            "Event",
            "Location",
            "Technology",
            "MathematicalObject",
            "Definition",
        ],
        "relationship_types": [
            "SUBCLASS_OF",
            "PART_OF",
            "RELATED_TO",
            "CAUSES",
            "PRODUCES",
            "REQUIRES",
            "OCCURS_IN",
            "DISCOVERED_BY",
            "DEFINES",
            "IS_A",
        ]
    }

    # Llama 3.3 70B: 128K context. chunk_size=1200 is the sweet spot with the
    # expanded schema (11 node types inflate the extraction prompt).
    chunk_splitter = FixedSizeSplitter(chunk_size=1200, chunk_overlap=100)
    schema = STATIC_SCHEMA_DEF if SCHEMA_CONFIG.name == "STATIC" else "EXTRACTED"

    kg_builder_pdf = SimpleKGPipeline(
        llm=llm,
        driver=neo4j_driver,
        embedder=embedder,
        entities=schema["node_types"],
        relations=schema["relationship_types"],
        prompt_template=PROMPT_TEMPLATE,
        from_pdf=True,
        text_splitter=chunk_splitter,
        perform_entity_resolution=True,
        on_error="IGNORE",
    )

    kg_builder_text = SimpleKGPipeline(
        llm=llm,
        driver=neo4j_driver,
        embedder=embedder,
        entities=schema["node_types"],
        relations=schema["relationship_types"],
        prompt_template=PROMPT_TEMPLATE,
        from_pdf=False,
        text_splitter=chunk_splitter,
        perform_entity_resolution=True,
        on_error="IGNORE",
    )

    return kg_builder_pdf, kg_builder_text


# -- Global pipeline state -----------------------------------------------------

encoder_llm = None
retriever_llm = None
embedder = None
kg_builder_pdf = None
kg_builder_text = None
retriever = None
PROCESS_CONTEXT = False


def init_globals():
    """Initialize or reinitialize all pipeline components if needed."""
    global encoder_llm, retriever_llm, embedder, kg_builder_pdf, kg_builder_text, retriever

    neo4j_driver = get_driver()
    driver_recreated = ensure_driver_connected()

    if encoder_llm is None or driver_recreated:
        encoder_llm, retriever_llm, embedder = initialize_models()
        kg_builder_pdf, kg_builder_text = setup_kg_pipeline(encoder_llm, embedder)
        retriever = create_retriever(neo4j_driver, embedder)


def generate_answer(query, retriever, llm, original_query: str = "") -> dict:
    return generate(llm, retriever, query, original_query=original_query)


# -- Main pipeline entry point ------------------------------------------------

def run_pipeline(question: str, fallback: str, use_global_kg: bool = False, status_callback=None) -> dict:
    """Run the full GraphRAG pipeline: extract → ingest → retrieve → answer."""
    init_globals()
    neo4j_driver = get_driver()

    query, text_context = extract_query_and_context(question)

    # Only ingest into the KG if the encoder found real context (not self-contained MCQs)
    context_was_extracted = bool(text_context)

    if not context_was_extracted:
        text_context = [question]
    else:
        if PROCESS_CONTEXT:
            if status_callback:
                status_callback({"type": "step", "step": 2})
                status_callback({"type": "thought", "step": 2, "message": f"I'm processing {len(text_context)} text chunk(s) for extraction."})
            _run_async(process_context(neo4j_driver, kg_builder_pdf=kg_builder_pdf, kg_builder_text=kg_builder_text, texts=text_context))
            if status_callback:
                status_callback({"type": "thought", "step": 2, "message": "I'm populating the Local Knowledge Graph with the entities and relationships I extracted."})
        time.sleep(2)

    success = False

    if status_callback:
        status_callback({"type": "step", "step": 2})

    graph_rag = GraphRAG(
        llm=retriever_llm,
        retriever=retriever,
        prompt_template=GRAPHRAG_TEMPLATE if fallback == "prolog-graphrag" else GRAPHRAG_FALLBACK_TEMPLATE
    )
    retriever_result = []
    try:
        graph_rag_results = graph_rag.search(query, retriever_config={'top_k': 5, 'use_global_kg': use_global_kg, 'status_callback': status_callback}, return_context=True)
        retriever_result = graph_rag_results.retriever_result
        answer_dict = graph_rag_results.answer
        answer = answer_dict.get("answer", "") if isinstance(answer_dict, dict) else str(answer_dict)
        logprobs = answer_dict.get("logprobs", {}) if isinstance(answer_dict, dict) else {}
        success = True
    except Exception as e:
        logger.error("Error during generation: %s", e)

    return {
        "query": query,
        "text_context": text_context,
        "answer": answer if success else "Error during generation.",
        "logprobs": logprobs if success else [],
        "retriever_results": retriever_result,
    }


# -- PDF ingestion entry point ------------------------------------------------

def ingest_pdf_files(file_paths: list[str]) -> list:
    """Synchronous wrapper to ingest PDF files into the knowledge graph."""
    init_globals()
    return _run_async(process_pdf_documents(kg_builder_pdf, file_paths=file_paths))


if __name__ == "__main__":
    init_globals()
    neo4j_driver = get_driver()
    _run_async(process_context(neo4j_driver, kg_builder_pdf=kg_builder_pdf, kg_builder_text=kg_builder_text, texts=[]))
    print("Initial context processing done.")