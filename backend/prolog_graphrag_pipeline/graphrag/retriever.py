"""Retriever setup and hybrid search for the GraphRAG pipeline.

This module creates Neo4j indexes, wires up a HybridRetriever, and
monkey-patches its ``search`` method to additionally query the KBPedia
global knowledge graph and perform MCQ-aware multi-query expansion.

Key moving parts:
  - ``create_retriever(driver, embedder)`` — the public factory used by
    ``graphrag_driver.py``.  Drops/recreates document indexes, then
    returns a HybridRetriever whose ``search`` is replaced with
    ``patched_hybrid_search``.
  - ``patched_hybrid_search`` — augments the default vector + fulltext
    search with KBPedia concept retrieval and per-MCQ-choice independent
    searches, then deduplicates and ranks the combined results.
"""

import re
import time
import types
import logging
from typing import List

from neo4j.exceptions import ServiceUnavailable, AuthError
from neo4j_graphrag.retrievers import HybridRetriever
from neo4j_graphrag.types import RetrieverResult, RetrieverResultItem

from .config import RETRIEVAL_QUERY, RETRIEVER

logger = logging.getLogger(__name__)


# ── Neo4j health & index management ─────────────────────────────────────

def check_db_health(driver) -> bool:
    """Verify that *driver* can reach the Neo4j instance."""
    try:
        driver.verify_connectivity()
        logger.info("Neo4j driver connected. Pre-flight check passed.")
        return True
    except (ServiceUnavailable, AuthError) as e:
        logger.error("Pre-flight check failed: %s", e)
        return False


def create_indexes(driver):
    """Create the vector and fulltext indexes used by the HybridRetriever."""
    from ..llm_config import EMBED_DIM

    driver.execute_query(f"""
        CREATE VECTOR INDEX documentsVectorIndex IF NOT EXISTS
        FOR (n:Chunk) ON (n.embedding)
        OPTIONS {{indexConfig: {{
          `vector.dimensions`: {EMBED_DIM},
          `vector.similarity_function`: 'cosine'
        }}}}
    """, database_="neo4j")

    driver.execute_query("""
        CREATE FULLTEXT INDEX documentsFulltextIndex IF NOT EXISTS 
        FOR (n:Chunk) ON EACH [n.text]
    """, database_="neo4j")


def wait_for_indexes(driver, timeout=30):
    """Block until both document indexes report ONLINE, or raise on timeout."""
    target_indexes = ['documentsVectorIndex', 'documentsFulltextIndex']
    start_time = time.time()

    while True:
        if time.time() - start_time > timeout:
            raise TimeoutError(f"Indexes failed to go ONLINE within {timeout} seconds.")

        records, _, _ = driver.execute_query(
            "SHOW INDEXES YIELD name, state WHERE name IN $names",
            names=target_indexes,
            database_="neo4j"
        )

        states = [record["state"] for record in records]
        if len(states) == 2 and all(s == "ONLINE" for s in states):
            break

        time.sleep(2)


# ── Query sanitisation ──────────────────────────────────────────────────

def _sanitize_lucene_query(query_text: str) -> str:
    """Escape Lucene reserved characters to prevent fulltext query parse errors."""
    special_chars = r'+-&|!(){}[]^"~*?:\/'
    sanitized = []
    for ch in query_text:
        if ch in special_chars:
            sanitized.append(f'\\{ch}')
        else:
            sanitized.append(ch)
    return ''.join(sanitized)


# ── Result deduplication ────────────────────────────────────────────────

def _deduplicate_items(items: List[RetrieverResultItem], limit: int) -> List[RetrieverResultItem]:
    """Deduplicate retriever results by normalised content, keep highest-score first.

    Each item's string content is whitespace-collapsed and used as a
    uniqueness signature.  Items are sorted by descending score before
    deduplication so the best-scored variant of any duplicate is kept.
    """
    items_sorted = sorted(
        items,
        key=lambda x: x.metadata.get('score', 0.0) if x.metadata else 0.0,
        reverse=True,
    )
    seen: set[str] = set()
    unique: list[RetrieverResultItem] = []

    for item in items_sorted:
        content_str = ""
        if hasattr(item, "content"):
            if isinstance(item.content, str):
                content_str = item.content
            elif hasattr(item.content, "get"):
                content_str = item.content.get("text", item.content.get("content", str(item.content)))
            else:
                content_str = str(item.content)

        if content_str:
            content_str = content_str.replace('\n', ' ').replace('  ', ' ')
        sig = content_str.strip()
        if sig and sig not in seen:
            seen.add(sig)
            unique.append(RetrieverResultItem(content=content_str, metadata=item.metadata))

    return unique[:limit]


# ── Monkey-patched search ───────────────────────────────────────────────

def patched_hybrid_search(self, query_text, top_k=8, **kwargs):
    """Augmented search combining local document retrieval with KBPedia.

    This replaces the default ``HybridRetriever.search`` at runtime.
    The augmented flow is:

    1. **KBPedia global KG search** (if ``use_global_kg=True``) — finds
       grounded concept definitions and triples from the pre-loaded
       KBPedia ontology in Neo4j.
    2. **Local document vector + fulltext search** — the original hybrid
       retriever over user-uploaded PDF chunks.
    3. **MCQ choice expansion** — if the query contains multiple-choice
       options (``A. … B. …``), each choice text is independently
       searched to ensure option-level coverage.
    4. **Deduplication and ranking** — results from all sources are
       merged, deduplicated, and capped.
    """
    safe_query = _sanitize_lucene_query(query_text)
    original_query = kwargs.pop("original_query", "")
    use_global_kg = kwargs.pop("use_global_kg", False)
    status_callback = kwargs.pop("status_callback", None)
    all_items: list[RetrieverResultItem] = []

    # 1. KBPedia global knowledge graph search
    if use_global_kg:
        try:
            if not hasattr(self, '_kbpedia_retriever'):
                from .kbpedia_retriever import KBPediaRetriever
                from .neo4j_manager import get_driver
                kb_driver = getattr(self, 'driver', None) or get_driver()
                kb_llm = getattr(self, 'llm', None)
                self._kbpedia_retriever = KBPediaRetriever(driver=kb_driver, llm=kb_llm, top_k=top_k)

            kb_result = self._kbpedia_retriever.search(
                query_text,
                top_k=top_k * 2,
                original_query=original_query,
                status_callback=status_callback,
            )
            if kb_result and kb_result.items:
                all_items.extend(kb_result.items)
                logger.debug("[Hybrid] KBPedia returned %d items.", len(kb_result.items))
                if status_callback:
                    status_callback({"type": "step", "step": 3})
                    status_callback({"type": "thought", "step": 3, "message": f"I checked the Global Knowledge Graph (KBPedia) and found {len(kb_result.items)} relevant definition/fact nodes."})
        except Exception as e:
            logger.debug("[Hybrid] KBPedia search error: %s", e)

    # 2. Local document search (main query)
    res_main = self._original_search(query_text=safe_query, top_k=top_k, **kwargs)
    raw_local_count = 0
    if res_main and res_main.items:
        all_items.extend(res_main.items)
        raw_local_count += len(res_main.items)

    # 3. MCQ choice expansion — run an independent search per choice
    mcq_choices = re.findall(r'\b[A-D][.)]\s*(.+)', original_query)
    if mcq_choices:
        logger.debug("[Hybrid] Extracted %d MCQ choices for independent search.", len(mcq_choices))
        if status_callback:
            status_callback({"type": "step", "step": 3})
            status_callback({"type": "thought", "step": 3, "message": f"I extracted {len(mcq_choices)} multiple-choice options to formulate independent vector searches for each."})
        choice_k = max(2, top_k // 2)
        for choice in mcq_choices:
            safe_choice = _sanitize_lucene_query(choice.strip())
            res_choice = self._original_search(query_text=safe_choice, top_k=choice_k, **kwargs)
            if res_choice and res_choice.items:
                all_items.extend(res_choice.items)
                raw_local_count += len(res_choice.items)

    if status_callback:
        status_callback({"type": "step", "step": 3})
        status_callback({"type": "thought", "step": 3, "message": f"My local vector search identified {raw_local_count} raw document chunks matching the query."})

    # 4. Deduplicate and rank
    unique_items = _deduplicate_items(all_items, top_k * 2)

    if status_callback:
        status_callback({"type": "step", "step": 3})
        status_callback({"type": "thought", "step": 3, "message": f"I optimized and deduplicated the results down to {len(unique_items)} unique highest-value entity chunks."})

    return RetrieverResult(items=unique_items, metadata={})


def expand_query(self, query):
    """Bypass LLM query expansion.

    The pipeline now relies on independent vector searches for each MCQ
    choice to guarantee comprehensive coverage, rather than LLM-extracted
    keywords.
    """
    return query


# ── Retriever factory ───────────────────────────────────────────────────

def create_retriever(driver, embedder):
    """Create a HybridRetriever with augmented search over documents and KBPedia.

    Steps:
      1. Verify Neo4j connectivity.
      2. Drop and recreate local document indexes (vector + fulltext).
      3. Wait for indexes to come online.
      4. Instantiate ``HybridRetriever`` and monkey-patch its ``search``
         method with ``patched_hybrid_search``.
    """
    if not check_db_health(driver):
        raise ConnectionError("Aborting initialization: Cannot connect to Neo4j.")

    # Drop and recreate local document indexes
    driver.execute_query("DROP INDEX documentsVectorIndex IF EXISTS")
    driver.execute_query("DROP INDEX documentsFulltextIndex IF EXISTS")
    create_indexes(driver)

    try:
        wait_for_indexes(driver, timeout=30)
    except TimeoutError as e:
        logger.error("Critical Error: %s", e)
        return None

    if RETRIEVER != "HybridRetriever":
        raise ValueError(f"Retriever {RETRIEVER} is invalid.")

    r = HybridRetriever(
        driver=driver,
        vector_index_name="documentsVectorIndex",
        fulltext_index_name="documentsFulltextIndex",
        embedder=embedder,
    )
    # Replace the default search with the augmented version
    r._original_search = r.search
    r.search = types.MethodType(patched_hybrid_search, r)
    return r