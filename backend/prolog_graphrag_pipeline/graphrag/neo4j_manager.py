"""Neo4j driver management and document CRUD operations."""

import logging
import time

import neo4j

from .config import NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

logger = logging.getLogger(__name__)

# Module-level driver instance (singleton)
neo4j_driver = None


def ensure_driver_connected() -> bool:
    """Ensure the Neo4j driver is connected. Returns True if a new connection was created."""
    global neo4j_driver
    MAX_RETRIES = 10
    RETRY_DELAY = 30

    for attempt in range(MAX_RETRIES):
        try:
            if neo4j_driver is not None:
                neo4j_driver.verify_connectivity()
                return False

            neo4j_driver = neo4j.GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
                connection_timeout=10.0,
                max_connection_lifetime=200,
                encrypted=False
            )
            neo4j_driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error("Could not connect to Neo4j (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, e)
            if neo4j_driver:
                try:
                    neo4j_driver.close()
                except Exception:
                    pass
            neo4j_driver = None

            if attempt < MAX_RETRIES - 1:
                logger.info("Retrying Neo4j connection in %ds...", RETRY_DELAY)
                time.sleep(RETRY_DELAY)
            else:
                raise ConnectionError(f"Failed to connect to Neo4j after {MAX_RETRIES} attempts: {e}") from e


def get_driver():
    """Return the current Neo4j driver, connecting if needed."""
    ensure_driver_connected()
    return neo4j_driver


def clear_local_data():
    """Delete pipeline-generated nodes/relationships, preserving KBPedia reference concepts."""
    ensure_driver_connected()
    logger.warning("Clearing pipeline data (preserving KBPedia)...")
    try:
        with neo4j_driver.session(database="neo4j") as session:
            session.run("MATCH (n) WHERE NOT n:KBPediaConcept DETACH DELETE n")
    except Exception as e:
        logger.error("Error clearing local data: %s", e)
    logger.info("Database cleared successfully (KBPedia preserved).")


def remove_document_from_kg(filename: str) -> dict:
    """Delete a Document and its Chunks from Neo4j by filename.

    Uses the FROM_DOCUMENT relationship to scope deletion.
    Does NOT affect KBPedia, Wikidata, or other document nodes.
    """
    ensure_driver_connected()
    try:
        with neo4j_driver.session(database="neo4j") as session:
            count_result = session.run("""
                MATCH (d:Document) WHERE d.path CONTAINS $filename
                OPTIONAL MATCH (c:Chunk)-[:FROM_DOCUMENT]->(d)
                RETURN count(DISTINCT d) as doc_count, count(DISTINCT c) as chunk_count
            """, filename=filename)
            counts = count_result.single()
            doc_count = counts["doc_count"] if counts else 0
            chunk_count = counts["chunk_count"] if counts else 0

            if doc_count == 0:
                return {"status": "not_found", "message": f"No document matching '{filename}' found in Neo4j."}

            session.run("""
                MATCH (d:Document) WHERE d.path CONTAINS $filename
                OPTIONAL MATCH (c:Chunk)-[:FROM_DOCUMENT]->(d)
                DETACH DELETE c, d
            """, filename=filename)

            logger.info("Removed document '%s': %d Document node(s), %d Chunk node(s) deleted.", filename, doc_count, chunk_count)
            return {
                "status": "removed",
                "filename": filename,
                "documents_deleted": doc_count,
                "chunks_deleted": chunk_count
            }
    except Exception as e:
        logger.error("Error removing document '%s': %s", filename, e)
        return {"status": "error", "message": str(e)}


def list_ingested_documents() -> list:
    """List all Document nodes currently in Neo4j with their chunk counts."""
    ensure_driver_connected()
    try:
        with neo4j_driver.session(database="neo4j") as session:
            result = session.run("""
                MATCH (d:Document)
                OPTIONAL MATCH (c:Chunk)-[:FROM_DOCUMENT]->(d)
                RETURN d.path as path, count(c) as chunk_count
                ORDER BY d.path
            """)
            return [{"path": record["path"], "chunk_count": record["chunk_count"]} for record in result]
    except Exception as e:
        logger.error("Error listing documents: %s", e)
        return []
