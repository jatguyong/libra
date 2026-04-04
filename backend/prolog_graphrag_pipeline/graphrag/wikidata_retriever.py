import asyncio
import aiohttp
import time
import logging
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RateLimitExceededException(Exception):
    pass

class WikidataRetriever:
    """
    Dedicated fetching module to retrieve Wikidata facts via SPARQL
    with rate limit protections, strict timeouts, and backoff logic.
    Converts results directly to valid Prolog assertions.
    """
    def __init__(self):
        self.endpoint_url = "https://query.wikidata.org/sparql"
        # Required Custom User-Agent by Wikidata Policy
        self.user_agent = "PrologGraphRAG_Agent/1.0 (Contact: local@example.org) Python/aiohttp"
        
        # Concurrency & Timeouts: No more than 5 parallel requests
        self.semaphore = asyncio.Semaphore(5)
        
        self.error_timestamps: List[float] = []

    async def _check_error_rate(self):
        """Halt and log if 30-error-per-minute threshold is approached."""
        now = time.time()
        # Keep only errors from the last 60 seconds
        self.error_timestamps = [t for t in self.error_timestamps if now - t < 60]
        if len(self.error_timestamps) >= 30:
            logger.error("Approaching 30-error-per-minute threshold. Halting requests to prevent IP ban.")
            raise RateLimitExceededException("Wikidata API error threshold exceeded (>30 errors/min).")

    def _record_error(self):
        self.error_timestamps.append(time.time())

    async def _fetch_facts_async(self, qid: str) -> List[str]:
        async with self.semaphore:
            sparql_query = f"""
            SELECT ?pLabel ?oLabel WHERE {{
              wd:{qid} ?p ?o.
              ?o rdfs:label ?oLabel.
              ?property wikibase:directClaim ?p.
              ?property rdfs:label ?pLabel.
              FILTER(LANG(?oLabel) = "en")
              FILTER(LANG(?pLabel) = "en")
            }} LIMIT 25
            """
            
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/sparql-results+json"
            }
            
            # Enforce strict 60-second timeout on all requests
            timeout = aiohttp.ClientTimeout(total=60)
            
            max_retries = 3
            for attempt in range(max_retries):
                await self._check_error_rate()
                
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(self.endpoint_url, params={"query": sparql_query}, headers=headers) as response:
                            if response.status == 200:
                                data = await response.json()
                                facts = []
                                for item in data.get("results", {}).get("bindings", []):
                                    predicate = item.get("pLabel", {}).get("value", "")
                                    obj = item.get("oLabel", {}).get("value", "")
                                    
                                    # Format as plain text facts for GraphRAG
                                    if predicate and obj:
                                        facts.append(f"{predicate.lower()}: {obj.lower()}")
                                        
                                return facts
                                
                            elif response.status == 429:
                                # Abort immediately instead of blocking the pipeline for 120s
                                logger.warning(f"HTTP 429 Too Many Requests from Wikidata for {qid}. Aborting fetch silently.")
                                return []
                            else:
                                self._record_error()
                                logger.error(f"HTTP {response.status} from Wikidata for {qid}")
                                break
                                
                except asyncio.TimeoutError:
                    self._record_error()
                    logger.error(f"Strict 60-second timeout reached querying Wikidata for {qid}")
                    break
                except Exception as e:
                    self._record_error()
                    logger.error(f"Error querying Wikidata for {qid}: {e}")
                    break
                    
            return []

    def retrieve_facts(self, qid: str) -> List[str]:
        """Synchronous wrapper for main pipeline."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.ensure_future(self._fetch_facts_async(qid))
                return loop.run_until_complete(task)
        except RuntimeError:
            pass
        return asyncio.run(self._fetch_facts_async(qid))

    # ── Wikidata REST Search API (for Q-ID discovery) ─────────────────────

    async def _search_entity_async(self, name: str, limit: int = 5) -> List[dict]:
        """
        Search Wikidata's REST API for entity candidates by label.
        Returns list of {qid, label, description}.
        """
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "limit": limit,
            "format": "json",
        }
        headers = {"User-Agent": self.user_agent}
        timeout = aiohttp.ClientTimeout(total=15)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        candidates = []
                        for item in data.get("search", []):
                            candidates.append({
                                "qid": item.get("id", ""),
                                "label": item.get("label", ""),
                                "description": item.get("description", ""),
                            })
                        return candidates
                    else:
                        self._record_error()
                        logger.error(f"Wikidata search API returned HTTP {response.status} for '{name}'")
        except Exception as e:
            self._record_error()
            logger.error(f"Wikidata search API error for '{name}': {e}")
        return []

    def search_entity(self, name: str, limit: int = 5) -> List[dict]:
        """Synchronous wrapper: search Wikidata for entity candidates by label."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.ensure_future(self._search_entity_async(name, limit))
                return loop.run_until_complete(task)
        except RuntimeError:
            pass
        return asyncio.run(self._search_entity_async(name, limit))

    # ── Targeted Structural SPARQL (pre-filtered at DB level) ─────────────

    # Core properties: ALWAYS fetched (fundamental ontological structure)
    CORE_PROPERTIES = ["P31", "P279", "P361", "P527", "P1542"] # instance of, subclass of, part of, has part, has effect


    # Extended properties: only fetched when LLM deems them relevant to the query.
    # Grouped by semantic category so the LLM picks categories, not raw P-codes.
    EXTENDED_PROPERTIES = {
        "causality":       ["P828", "P1542"],   # has cause, has effect
        "sequence":        ["P155", "P156"],     # follows, followed by
        "differentiation": ["P1889", "P460"],    # different from, said to be the same as
        "academic":        ["P2579", "P921"],     # studied in, main subject
        "composition":     ["P527", "P1269"],     # has part, facet of
        "function":        ["P366", "P1056"],     # has use, product/material produced
    }

    async def _fetch_structural_facts_async(self, qid: str, extra_properties: list = None) -> List[str]:
        """
        Fetch structurally useful Wikidata properties for Prolog reasoning.
        Always fetches CORE_PROPERTIES. If extra_properties is provided,
        those P-codes are added to the SPARQL VALUES clause.
        """
        # Merge core + extra, deduplicate
        all_pids = list(set(self.CORE_PROPERTIES + (extra_properties or [])))
        values_clause = " ".join([f"wdt:{pid}" for pid in all_pids])

        async with self.semaphore:
            sparql_query = f"""
            SELECT ?pLabel ?oLabel ?desc WHERE {{
              {{
                # Fetch structural facts
                VALUES ?p {{ {values_clause} }}
                wd:{qid} ?p ?o.
                ?o rdfs:label ?oLabel.
                ?property wikibase:directClaim ?p.
                ?property rdfs:label ?pLabel.
                FILTER(LANG(?oLabel) = "en")
                FILTER(LANG(?pLabel) = "en")
              }}
              UNION
              {{
                # Fetch the text description of the entity
                wd:{qid} schema:description ?desc.
                FILTER(LANG(?desc) = "en")
              }}
            }} LIMIT 10
            """

            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/sparql-results+json"
            }
            timeout = aiohttp.ClientTimeout(total=30)

            max_retries = 2
            for attempt in range(max_retries):
                await self._check_error_rate()
                try:
                    async with aiohttp.ClientSession(timeout=timeout) as session:
                        async with session.get(self.endpoint_url, params={"query": sparql_query}, headers=headers) as response:
                            if response.status == 200:
                                data = await response.json()
                                facts = []
                                for item in data.get("results", {}).get("bindings", []):
                                    desc = item.get("desc", {}).get("value", "")
                                    if desc and f"defines: {desc.lower()}" not in facts:
                                        facts.insert(0, f"defines: {desc.lower()}") # Prioritize definition
                                        
                                    predicate = item.get("pLabel", {}).get("value", "")
                                    obj = item.get("oLabel", {}).get("value", "")
                                    # Python-level pre-filter: skip if object looks like a Q-ID with no label
                                    if predicate and obj and not obj.startswith("Q") and len(facts) < 10:
                                        fact_str = f"{predicate.lower()}: {obj.lower()}"
                                        if fact_str not in facts:
                                            facts.append(fact_str)
                                return facts
                            elif response.status == 429:
                                logger.warning(f"HTTP 429 Too Many Requests on structural SPARQL for {qid}. Aborting silently.")
                                return []
                            else:
                                self._record_error()
                                logger.error(f"HTTP {response.status} from structural SPARQL for {qid}")
                                break
                except asyncio.TimeoutError:
                    self._record_error()
                    logger.error(f"Structural SPARQL timeout for {qid}")
                    break
                except Exception as e:
                    self._record_error()
                    logger.error(f"Structural SPARQL error for {qid}: {e}")
                    break
            return []

    def retrieve_structural_facts(self, qid: str, extra_properties: list = None) -> List[str]:
        """Synchronous wrapper: fetch structural Wikidata triples with optional extra properties."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                task = asyncio.ensure_future(self._fetch_structural_facts_async(qid, extra_properties))
                return loop.run_until_complete(task)
        except RuntimeError:
            pass
        return asyncio.run(self._fetch_structural_facts_async(qid, extra_properties))
