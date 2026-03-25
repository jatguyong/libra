"""
Grounded KBPedia Retriever
Queries KBPedia concepts stored in Neo4j (:KBPediaConcept nodes).

Two modes (controlled by `triple_filter` at construction time):
  triple_filter=False (default, FAST):
    - Entity extraction: keyword-based, zero LLM calls
    - Concept selection:  ONE LLM call at the end to filter all candidates at once
  triple_filter=True (RIGOROUS, highest quality):
    - Entity extraction: LLM extracts entities + MCQ choices
    - Triple selection:  LLM keeps only query-relevant triples per concept (N calls)
"""

import json
import re
import time
from typing import List, Dict, Any, Optional
import logging
from ..llm_config import log_llm_event, retry_with_exponential_backoff

logger = logging.getLogger(__name__)


def _safe_parse_json(text: str, expect: type = None):
    """Robustly extract and parse the first complete JSON value from LLM output.
    - Strips markdown fences.
    - Finds the first '{' (for dict) or '[' (for list) and stops after the matching close.
    - Uses raw_decode so trailing text/extra objects never cause 'Extra data' errors.
    - Returns None on empty input or parse failure instead of raising."""
    if not text or not text.strip():
        return None
    # Strip markdown fences
    t = text.strip()
    if "```json" in t:
        t = t.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in t:
        t = t.split("```", 1)[1].split("```", 1)[0].strip()
    if not t:
        return None
    # Find the first opening char based on expected type
    opener = '{' if expect is dict else ('[' if expect is list else None)
    if opener is None:
        # Auto-detect: whichever comes first
        i_brace = t.find('{')
        i_bracket = t.find('[')
        if i_brace == -1 and i_bracket == -1:
            return None
        if i_brace == -1:
            pos = i_bracket
        elif i_bracket == -1:
            pos = i_brace
        else:
            pos = min(i_brace, i_bracket)
    else:
        pos = t.find(opener)
        if pos == -1:
            return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(t, pos)
        return obj
    except (json.JSONDecodeError, ValueError):
        return None


class KBPediaRetriever:
    """
    Retrieves grounded knowledge from KBPedia concepts stored in Neo4j.
    Fast mode (triple_filter=False, default): keyword entity extraction + single end-of-search LLM filter.
    Rigorous mode (triple_filter=True): LLM entity extraction + per-concept LLM triple filtering.
    """

    _index_verified = False

    def __init__(self, driver, llm=None, top_k: int = 4, embedder=None):
        self.driver  = driver
        self.embedder = embedder
        
        try:
            from .config import ENABLE_LLM_FILTERING, ENABLE_WIKIDATA_FALLBACK
        except (ModuleNotFoundError, ImportError):
            try:
                from graphrag.config import ENABLE_LLM_FILTERING, ENABLE_WIKIDATA_FALLBACK
            except ImportError:
                ENABLE_LLM_FILTERING = True
                ENABLE_WIKIDATA_FALLBACK = True

        # Nullify LLM if the global config toggle is disabled
        self.llm = llm if ENABLE_LLM_FILTERING else None
        self.enable_wikidata = ENABLE_WIKIDATA_FALLBACK
        
        self.top_k   = top_k

    def _verify_index(self):
        """Check once whether the KBPedia vector index exists."""
        if KBPediaRetriever._index_verified:
            return True
        try:
            records, _, _ = self.driver.execute_query(
                "SHOW VECTOR INDEXES YIELD name WHERE name = 'kbpediaConceptVectorIndex' RETURN name",
                database_="neo4j",
            )
            if records:
                KBPediaRetriever._index_verified = True
                return True
            else:
                print("DEBUG PROLOG-GRAPHRAG:KBPedia vector index 'kbpediaConceptVectorIndex' not found. "
                      "Run kbpedia_loader.py first to embed KBPedia concepts.")
                return False
        except Exception as e:
            logger.debug(f"Error verifying KBPedia vector index: {e}")
            return False

    def _vector_search(self, query_vector: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        """Vector similarity search against KBPedia concepts."""
        if not query_vector:
            return []

        try:
            records, _, _ = self.driver.execute_query(
                """
                CALL db.index.vector.queryNodes('kbpediaConceptVectorIndex', $limit, $vector)
                YIELD node, score
                RETURN node.uri AS uri, node.name AS name, node.definition AS definition,
                       node.altLabels AS altLabels, score
                """,
                vector=query_vector,
                limit=limit,
                database_="neo4j",
            )
            results = []
            for r in records:
                results.append({
                    "uri": r["uri"],
                    "name": r["name"],
                    "definition": r["definition"] or "",
                    "altLabels": r["altLabels"] or [],
                    "score": r["score"],
                })
            return results
        except Exception as e:
            logger.debug(f"KBPedia concept vector search error: {e}")
            return []

    def extract_entities(self, query: str) -> List[str]:
        """
        Hybrid entity extraction:
        1. Uses Regex to accurately pull exact MCQ choices (fast and prevents LLM formatting crashes).
        2. Uses LLM to extract explicit entities and implied conceptual terms from the question stem.
        3. Combines and prioritizes the lists.
        """
        # --- 1. Regex MCQ Extraction ---
        mcq_choices = [c.strip() for c in re.findall(r'\b[A-D][.)]\s*(.+?)(?=\s+\b[A-D][.)]|$)', query)]
        # Clean up any trailing punctuation from choices
        mcq_choices = [re.sub(r'[?!.]+$', '', c).strip().lower() for c in mcq_choices if c.strip()]
        
        # --- 2. LLM Conceptual Extraction ---
        llm_entities = []
        if self.llm:
            # We provide the FULL query (stem + options) to the LLM so it can deduce context
            # and extract underlying concepts from the answer choices as well.
            prompt = f"""You are extracting search terms for a knowledge base lookup.

Given this query (which may include multiple-choice options), extract the following:
1. **Explicit entities** mentioned in the question stem (e.g., "plant cell", "animal skeleton")
2. **Implied functional concepts** the question is asking about (e.g., "photosynthesis")
3. **Core scientific terms** from the answer options. If an option is a long sentence like "Dogs are better than cats", extract only the core entities ("Dogs", "cats").

Query: "{query}"

Output a plain JSON list of strings. Include 4-8 terms maximum.
Example: ["plant cell", "structural support", "cell wall", "chloroplast"]"""
            
            try:
                response = self.llm.invoke(prompt)
                res_text = (response.content if hasattr(response, 'content') else str(response)).strip()
                
                # Robust JSON extraction: Find first '[' and last ']'
                bracket_start = res_text.find('[')
                bracket_end = res_text.rfind(']')
                
                if bracket_start != -1 and bracket_end != -1:
                    json_str = res_text[bracket_start:bracket_end + 1]
                    parsed = json.loads(json_str)
                    if isinstance(parsed, list):
                        llm_entities = [str(item).lower() for item in parsed]
                else:
                    logger.debug(f"Entity extraction LLM returned no JSON array. Raw: {repr(res_text[:100])}")
            except Exception as e:
                logger.debug(f"KBPedia entity extraction LLM failed: {e}")

        # --- 3. Fallback ---
        # If LLM fails or is missing, use basic word splitting for the stem
        if not llm_entities:
            stem = re.sub(r'\b[A-D][.)]\s?', ' ', query)
            stem = re.sub(r'[?!,;:()\[\]]', ' ', stem).replace('\n', ' ')
            words = [w.strip('.').lower() for w in stem.split() if len(w) >= 5]
            llm_entities = words[:5]

        # --- 4. Combine and deduplicate ---
        unique_entities = []
        seen = set()
        
        # Prioritize MCQ choices first, then LLM concepts
        for phrase in mcq_choices + llm_entities:
            if phrase and phrase not in seen:
                seen.add(phrase)
                unique_entities.append(phrase)
                
        # We don't want to sort by length anymore because LLM gives high-quality short phrases too.
        # MCQ choices naturally stay at the top.
        
        return unique_entities[:10]



    def find_concepts(self, search_term: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Fulltext search on KBPediaConcept nodes.
        Fuzzy fallback: if the exact phrase returns nothing, tries only the LONGEST
        word in the phrase (most specific/rare) rather than all words left-to-right.
        This prevents generic words like 'skeleton' from matching off-topic concepts
        like 'skeleton tarantula' when the original intent was 'animal skeleton'.
        """
        results = self._fulltext_search(search_term, limit)

        # Fuzzy fallback: use only the longest (most specific) word
        if not results and ' ' in search_term:
            words = [w for w in search_term.split() if len(w) > 3]
            if words:
                # Sort by length descending — longer word = more specific/rare
                longest_word = sorted(words, key=len, reverse=True)[0]
                logger.debug(f"KBPedia exact search failed for '{search_term}'. Trying longest-word fallback: '{longest_word}'")
                results = self._fulltext_search(longest_word, limit=limit)

        return results

    def _fulltext_search(self, term: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Raw fulltext search against the index."""
        # Sanitize for Lucene
        safe_term = term.replace('"', '').replace('\\', '').replace('~', '').replace('*', '')
        safe_term = re.sub(r'[+\-!(){}[\]^"~*?:\\/]', ' ', safe_term).strip()
        if not safe_term:
            return []

        try:
            records, _, _ = self.driver.execute_query(
                """
                CALL db.index.fulltext.queryNodes('kbpediaConceptIndex', $term)
                YIELD node, score
                RETURN node.uri AS uri, node.name AS name, node.definition AS definition,
                       node.altLabels AS altLabels, score
                ORDER BY score DESC
                LIMIT $limit
                """,
                term=safe_term,
                limit=limit,
                database_="neo4j",
            )
            results = []
            for r in records:
                results.append({
                    "uri": r["uri"],
                    "name": r["name"],
                    "definition": r["definition"] or "",
                    "altLabels": r["altLabels"] or [],
                    "score": r["score"],
                })
            return results
        except Exception as e:
            logger.debug(f"KBPedia concept search error for '{safe_term}': {e}")
            return []

    def get_neighborhood(self, uri: str) -> List[str]:
        """Get the ontology neighborhood of a concept. Reduced strictly to immediate parent to minimize noise."""
        try:
            records, _, _ = self.driver.execute_query(
                """
                MATCH (n:KBPediaConcept {uri: $uri})
                OPTIONAL MATCH (n)-[:SUBCLASS_OF]->(ancestor:KBPediaConcept)
                OPTIONAL MATCH (descendant:KBPediaConcept)-[:SUBCLASS_OF]->(n)
                RETURN 
                    collect(DISTINCT {name: ancestor.name})[0..2] AS ancestors,
                    collect(DISTINCT {name: descendant.name})[0..2] AS descendants
                """,
                uri=uri,
                database_="neo4j",
            )

            triples = []
            if records:
                row = records[0]
                for a in row.get("ancestors", []):
                    if a and a.get("name"):
                        triples.append(f"subclass of: {a['name']}")
                for d in row.get("descendants", []):
                    if d and d.get("name"):
                        triples.append(f"has subclass: {d['name']}")
            return triples
        except Exception as e:
            logger.debug(f"KBPedia neighborhood error: {e}")
            return []

    def filter_triples_for_query(self, query: str, entity_label: str, triples: List[str], original_query: str = "") -> List[str]:
        """Use LLM to keep only logically relevant triples."""
        if not self.llm or not triples:
            return triples[:15]

        # Use the full original prompt (with MCQ choices) when available for better filtering
        filter_query = original_query if original_query else query

        triples_text = "\n".join([f"- {t}" for t in triples])
        prompt = f"""Task: You are deeply integrated into a Prolog GraphRAG pipeline.
Below is a list of known facts (triples) about the entity '{entity_label}'.
Your job is to strictly filter these facts and select ONLY the ones that are logically relevant or useful to answer the user's query.
Irrelevant facts will poison the logic engine, so drop anything that doesn't help.

User Query: "{filter_query}"

Facts about {entity_label}:
{triples_text}

Output format: A JSON list of strings containing exactly the original facts you deemed relevant.
Example: ["subclass of: Structural Component", "ancestor definition: provides support"]
If none are relevant, output an empty list [].
"""
        try:
            raw = self.llm.invoke(prompt)
            # .content may exist (LLM response object) or it may already be a plain string
            res = (raw.content if hasattr(raw, 'content') else str(raw)).strip()
            logger.debug(f"Triple filter raw response for '{entity_label}': {repr(res[:200])}")

            # Strip markdown code fences
            if "```json" in res:
                res = res.split("```json")[1].split("```")[0].strip()
            elif "```" in res:
                res = res.split("```")[1].split("```")[0].strip()

            # Guard: GraphRAGLLM._clean_response_text() strips everything outside {},
            # so a JSON array comes back empty. Try to find brackets first.
            bracket_start = res.find('[')
            bracket_end = res.rfind(']')
            if bracket_start != -1 and bracket_end != -1:
                res = res[bracket_start:bracket_end + 1]
            elif not res:
                logger.debug(f"Triple filter got empty response for '{entity_label}'. Using all raw triples.")
                return triples

            filtered = json.loads(res)
            if isinstance(filtered, list):
                return filtered
        except Exception as e:
            logger.debug(f"Triple filtering failed for '{entity_label}': {e}. Using all raw triples.")

        return triples

    def filter_triples_batch(self, query: str, concepts_data: List[Dict[str, Any]], original_query: str = "", status_callback=None) -> Dict[str, List[str]]:
        """
        Use LLM to keep only logically relevant triples for MULTIPLE concepts at once.
        concepts_data is a list of dicts: {"name": str, "triples": List[str]}
        Returns a dictionary mapping concept_name to a list of filtered triples.
        """
        if not self.llm or not concepts_data:
            return {c["name"]: c["triples"][:15] for c in concepts_data}
            
        if status_callback:
            total_triples = sum(len(c["triples"][:12]) for c in concepts_data)
            status_callback({"type": "thought", "step": 4, "message": f"Triple Filter: Scanning {total_triples} raw factual triples related to these entities to purge generic taxonomies and noisy metadata..."})

        filter_query = original_query if original_query else query

        # Build the payload for the prompt
        MAX_TRIPLES_PER_CONCEPT = 12
        concepts_text = ""
        for c in concepts_data:
            capped_triples = c["triples"][:MAX_TRIPLES_PER_CONCEPT]
            triples_text = "\n".join([f"  - {t}" for t in capped_triples])
            concepts_text += f"Concept: '{c['name']}'\nFacts:\n{triples_text}\n\n"

        # First, analyse what the query actually needs — state this explicitly in the prompt
        prompt = f"""You are a ruthless logical fact filter for a Prolog reasoning engine.
Your ONLY job: given a user question and raw knowledge-graph triples, keep ONLY the facts that are DIRECTLY REQUIRED to derive an answer.

## User Question
"{filter_query}"

## What does answering this question require?
Think carefully: what are the EXACT scientific laws, definitions, or relationships needed?
Any fact that doesn't contribute to deriving that answer is NOISE — discard it.

## Raw Concepts and Facts
{concepts_text}

## RUTHLESS DISCARD RULES (apply all, no exceptions):
1. DROP any structural/taxonomic fact: "subclass of:", "instance of:", "type of:", "part of a set of:", "collection of all"
2. DROP any Wikidata property whose value is a generic category (e.g., "subclass of: liquid", "instance of: chemical substance") — unless that specific category is essential to the reasoning chain.
3. DROP any identifier, external ID, administrative or database reference.
4. DROP any "different from:", "said to be the same as:", or disambiguation-only facts.
5. DROP "has use:", "has part(s):" unless the specific part/use is directly relevant to the question.
6. DROP any fact about a concept that is not mentioned in or directly implied by the question.
7. KEEP only facts that express a LAW, RULE, or QUANTITATIVE RELATIONSHIP that the Prolog engine can use.
8. If a concept has NO relevant facts, return an empty list `[]` — do NOT invent fallbacks.
9. Keep at most 5 facts per concept. If more pass, keep only the top 5 most relevant.

Output: a JSON dictionary — keys are concept names, values are lists of kept fact strings.
Only output JSON. No explanation or commentary.
Example:
{{
  "ammonia": ["definition: a colorless gas with molecular formula NH3"],
  "carbon dioxide": ["definition: a gas with molecular formula CO2"],
  "ideal gas law": ["equal volumes of gas at same T and P contain equal numbers of molecules (Avogadro's Law)"],
  "water": []
}}
"""
        # Default fallback
        result_map = {c["name"]: c["triples"] for c in concepts_data}

        max_retries = 3
        for attempt in range(max_retries):
            try:
                start_time = time.perf_counter()
                raw = self.llm.invoke(prompt)
                duration = time.perf_counter() - start_time
                log_llm_event(f"KBPEDIA_TRIPLE_FILTER_BATCH_{len(concepts_data)}", duration=duration)
                
                res = (raw.content if hasattr(raw, 'content') else str(raw)).strip()
                safe_res = str(res[:200]).encode('ascii', 'replace').decode('ascii')
                logger.debug(f"Batch triple filter raw response: {repr(safe_res)}...")

                if "```json" in res:
                    res = res.split("```json")[1].split("```")[0].strip()
                elif "```" in res:
                    res = res.split("```")[1].split("```")[0].strip()

                bracket_start = res.find('{')
                bracket_end = res.rfind('}')
                if bracket_start != -1 and bracket_end != -1:
                    res = res[bracket_start:bracket_end + 1]
                elif not res:
                    logger.debug(f"Batch triple filter got empty response. Using all raw triples.")
                    return result_map

                filtered = _safe_parse_json(res, expect=dict)
                if isinstance(filtered, dict):
                    for c in concepts_data:
                        name = c["name"]
                        if name in filtered and isinstance(filtered[name], list):
                            # Clean up formatting artifacts (like "- subclass of:" -> "subclass of:")
                            cleaned_triples = [t[2:].strip() if t.startswith("- ") else t.strip() for t in filtered[name]]
                            result_map[name] = cleaned_triples
                            kept_triples += len(cleaned_triples)
                            
                    if status_callback:
                        status_callback({"type": "thought", "step": 4, "message": f"Discarded {total_triples - kept_triples} noisy properties, finalizing a set of {kept_triples} high-signal logical facts."})
                    return result_map # Return immediately on success
            except Exception as e:
                logger.debug(f"Batch triple filtering attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(3)
                else:
                    logger.debug(f"All {max_retries} batch filtering attempts failed. Using all raw triples.")

        return result_map


    def filter_wikidata_triples(self, query: str, concept_name: str, wikidata_facts: list) -> list:
        """
        Dedicated, per-concept LLM filter for raw Wikidata triples.
        Runs immediately after Wikidata augmentation — BEFORE facts are merged with KBPedia triples.

        Applies extremely strict rules:
        - Must be a direct scientific/definitional property needed to answer the query
        - Drops ALL taxonomic, disambiguation, use-case, part-of, and identifier facts
        - Returns at most 3 facts per concept
        - Returns [] if nothing is truly necessary
        """
        if not self.llm or not wikidata_facts:
            return wikidata_facts

        # Hard-coded regex pre-filter: drop obviously useless property types before LLM sees them
        ALWAYS_DROP_PATTERNS = [
            r'^(subclass of|instance of|part of|facet of|said to be the same as|different from):',
            r'^(has use|use|used by):\s',
            r'^(Wikimedia|Commons|wikidata|external|identifier|ID|database|catalog):',
            r'^(described by source|topic.s main template|topic.s main Wikimedia)\b',
            r'^(OmegaWiki|Freebase|UMLS|CAS|InChI|ChemSpider|PubChem|BabelNet)',
        ]
        import re as _re
        pre_filtered = []
        for fact in wikidata_facts:
            lower = fact.lower()
            if any(_re.search(p, lower) for p in ALWAYS_DROP_PATTERNS):
                continue
            pre_filtered.append(fact)

        if not pre_filtered:
            return []

        facts_text = "\n".join([f"  {i+1}. {f}" for i, f in enumerate(pre_filtered)])

        prompt = f"""You are a precision Wikidata fact filter for a Prolog logic engine.
Before filtering, you MUST reason about what the question is actually asking and what kind of knowledge is needed to answer it.

## User Question
"{query}"

## Concept Being Evaluated
"{concept_name}"

## Step 1 — Pre-Reasoning (REQUIRED before filtering)
Answer these three questions in 1-2 sentences each:
A) What is the CORE thing this question is asking? (e.g. "It asks whether two gas samples have the same, more, or fewer particles")
B) What is the LIKELY ANSWER and what specific knowledge supports it? (e.g. "Avogadro's Law: equal V, T, P → equal particle count → same number")
C) For the concept "{concept_name}", what EXACT property or fact would contribute to that reasoning chain? If no property of this concept is part of the reasoning chain, state "NONE".

## Step 2 — Filter these Wikidata facts
{facts_text}

## Filtering Rules (apply AFTER completing Step 1):
- Keep a fact ONLY if it directly appears in the reasoning chain you described in Step 1C.
- DROP facts about: use-cases, applications, environmental impact, part-of, made-from, industry classification.
- DROP facts about: taxonomic hierarchy, disambiguation, historical/cultural context.
- DROP facts where the VALUE is a generic object, category, or anything not numerically/chemically specific.
- If Step 1C was "NONE", return [] immediately.
- Maximum 3 facts to keep. If more pass, choose the 3 most directly useful to the reasoning.

## Output format
First write your Step 1 reasoning (A, B, C), then on a new line output ONLY a JSON list:
["fact string verbatim from input", ...]
or [] if nothing qualifies.

IMPORTANT: The JSON list must be the LAST thing you output. Only include facts copied verbatim from the numbered list above.
"""

        try:
            import time as _time
            start = _time.perf_counter()
            raw = self.llm.invoke(prompt)
            duration = _time.perf_counter() - start
            log_llm_event("WIKIDATA_TRIPLE_FILTER", duration=duration)

            res = (raw.content if hasattr(raw, 'content') else str(raw)).strip()
            if '```json' in res:
                res = res.split('```json', 1)[1].split('```', 1)[0].strip()
            elif '```' in res:
                res = res.split('```', 1)[1].split('```', 1)[0].strip()

            # The CoT prompt emits reasoning THEN the JSON list last — use rfind to get the last [...] block
            bracket_end = res.rfind(']')
            bracket_start = res.rfind('[', 0, bracket_end + 1) if bracket_end != -1 else -1
            if bracket_start != -1 and bracket_end != -1:
                res = res[bracket_start:bracket_end + 1]
                parsed = _safe_parse_json(res, expect=list)
                if isinstance(parsed, list):
                    # Validate that returned strings are actual substrings of pre_filtered
                    valid = [f for f in parsed if isinstance(f, str) and any(f.strip() in pf for pf in pre_filtered)]
                    logger.debug(f"[WikidataFilter] '{concept_name}': kept {len(valid)}/{len(wikidata_facts)} wikidata facts.")
                    return valid
        except Exception as e:
            logger.debug(f"[WikidataFilter] Failed for '{concept_name}': {e}. Returning pre-filtered subset.")

        # Fallback: return regex-pre-filtered (already dropped worst offenders), capped at 3
        return pre_filtered[:3]


    @staticmethod
    def _hard_filter_triples(triples: list, concept_name: str) -> list:
        """
        Deterministic, LLM-free filter applied to ALL triples (KBPedia + Wikidata).
        Unconditionally drops patterns that are NEVER useful in a Prolog reasoning engine,
        regardless of what the LLM decided upstream.
        """
        import re as _re

        # Patterns applied to the raw fact string (after stripping '(Wikidata)' prefix)
        HARD_DROP = [
            # Taxonomy / ontology structure
            r'^subclass of:',
            r'^instance of:',
            r'^part of a set of:',
            r'^facet of:',
            r'^collection of',
            # Disambiguation
            r'^different from:',
            r'^said to be the same as:',
            r'^possible unification with:',
            # Use-cases / applications
            r'^has use:',
            r'^used by:',
            r'^has effect:',
            r'^part of:',          # e.g. "part of: air pollution", "part of: methanogenesis"
            # External/database references
            r'^defines:',          # e.g. "(Wikidata) defines: chemical compound" — tautological
            r'\bwikimedia\b',
            r'\bwikiproject\b',
            r'\bfreebase\b',
            r'\bumls\b',
            r'\bcas number\b',
            r'\binchi\b',
            r'\bpubchem\b',
            r'\bchemspider\b',
            # Part-of relationships only drop if value is clearly not a chemical property
            r'^has part\(s\):\s*(water|hydrogen|carbon|nitrogen|oxygen|iodine)$',  # too generic for gas comparison
        ]
        HARD_DROP_COMPILED = [_re.compile(p, _re.IGNORECASE) for p in HARD_DROP]

        # Strip the "(Wikidata)" prefix for matching, then match
        def _should_drop(triple: str) -> bool:
            normalised = _re.sub(r'^\(Wikidata\)\s*', '', triple).strip()
            return any(pat.search(normalised) for pat in HARD_DROP_COMPILED)

        kept = [t for t in triples if not _should_drop(t)]
        dropped = len(triples) - len(kept)
        if dropped:
            logger.debug(f"[HardFilter] '{concept_name}': dropped {dropped}/{len(triples)} junk triples.")
        return kept


    def _filter_concepts_once(self, query_text: str, candidates: list, original_query: str = "", status_callback=None) -> list:
        """
        Single LLM call to filter all candidates at once.
        `candidates` is a list of dicts: {name, uri, definition, triples}.
        `original_query` is the full user prompt including MCQ choices (when available).
        Returns a filtered list of dicts containing only relevant candidates.
        """
        if not self.llm or not candidates:
            return candidates
        if status_callback:
            status_callback({"type": "step", "step": 4})
            status_callback({"type": "thought", "step": 4, "message": f"I'm filtering {len(candidates)} raw concept matches to reduce noise..."})

        # Use the full original prompt (with MCQ choices) when available for better filtering
        filter_query = original_query if original_query else query_text

        # Extract MCQ choices from the question so the LLM knows to keep them
        mcq_choices = re.findall(r'\b[A-D][.)]\s*(.+)', filter_query)
        mcq_hint = ""
        if mcq_choices:
            mcq_hint = (
                f"\n\n### MCQ Answer Choices Detected\n"
                f"The question has these answer options: {mcq_choices}\n"
                f"You MUST keep any concept whose name or definition relates to ANY of these choices, even loosely. "
                f"These are exactly the concepts the Prolog engine needs to reason about.\n"
            )

        summary_lines = []
        for idx, c in enumerate(candidates):
            defn = (c.get("definition") or "")[:400]
            summary_lines.append(f"[{idx}] {c['name']}: {defn}")
        summary_text = "\n".join(summary_lines)

        prompt = f"""You are a strict relevance filter for a logic reasoning engine.
Only keep concepts whose facts are ESSENTIAL to answer the question.

User question: "{filter_query}"{mcq_hint}

Candidates (index: concept name: short definition):
{summary_text}

### DECISION RULE — Keep a concept ONLY if ALL of the following are true:
1. The concept's name or definition refers to EXACTLY ONE of the specific entities, substances, laws, or phenomena explicitly mentioned in the question.
   - "ammonia solution" does NOT qualify for a question about "ammonia gas" — they are different substances.
   - "sample (material)" does NOT qualify just because the question uses the word "sample".
2. Facts about this concept would appear in the LOGICAL PROOF needed to derive the answer.
3. The concept is NOT a vague superthing (e.g. "chemical entity", "concentration per volume", "simple substance").

### Reject if:
- The concept shares only a keyword with the question but describes a DIFFERENT thing (e.g. ammonia solution ≠ ammonia gas).
- The concept is entirely generic or taxonomic.
- The concept is one of {len(candidates)} candidates and clearly less relevant than others covering the same entity.

Return a JSON list of the RELEVANT indices (integers). Example: [0, 2]
Output ONLY the JSON list. If none are sufficiently relevant, output [].
"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                start_time = time.perf_counter()
                raw = self.llm.invoke(prompt)
                duration = time.perf_counter() - start_time
                log_llm_event("KBPEDIA_CONCEPT_FILTER", duration=duration)
                
                res = (raw.content if hasattr(raw, 'content') else str(raw)).strip()
                if "```" in res:
                    res = res.split("```")[1].split("```")[0].strip()
                bracket_start = res.find('[')
                bracket_end = res.rfind(']')
                if bracket_start != -1 and bracket_end != -1:
                    res = res[bracket_start:bracket_end + 1]
                indices = _safe_parse_json(res, expect=list)
                if not isinstance(indices, list):
                    raise ValueError(f"LLM did not return a list: {repr(res[:100])}")
                
                kept_candidates = [candidates[i] for i in indices if isinstance(i, int) and 0 <= i < len(candidates)]
                logger.debug(f"End-filter LLM kept indices: {indices} from {len(candidates)} candidates.")
                if status_callback:
                    status_callback({"type": "thought", "step": 4, "message": f"Concept Filter: I systematically rejected {len(candidates) - len(kept_candidates)} irrelevant concepts and kept {len(kept_candidates)} highly relevant core entities."})
                return kept_candidates
            except Exception as e:
                logger.debug(f"End-filter LLM attempt {attempt + 1}/{max_retries} failed: {e}.")
                if attempt < max_retries - 1:
                    time.sleep(3)
                else:
                    logger.debug(f"All {max_retries} end-filter attempts failed. Returning all candidates.")
        return candidates

    def search(self, query_text: str, top_k: int = 5, original_query: str = "", seeded_entities: List[str] = None, status_callback=None) -> Any:
        from .retriever import RetrieverResult, RetrieverResultItem

        if not self._verify_index():
            return RetrieverResult(items=[], metadata={})

        # `original_query` = full user prompt (with MCQ choices) for LLM filtering.
        filter_query = original_query if original_query else query_text

        # ── Vector Search ───────────────────────────────────────────────────
        logger.debug(f"[KBPedia] Computing query embeddings to search KBPedia concepts...")
        matches = []
        try:
            # Prepare the embedder function once
            from sentence_transformers import SentenceTransformer
            print("DEBUG PROLOG-GRAPHRAG:[KBPedia] Forcing local SentenceTransformer for 384D KBPedia index.", flush=True)
            temp_embedder = SentenceTransformer("all-MiniLM-L6-v2")
            embedder_fn = lambda text: temp_embedder.encode(text).tolist()

            # Schedule searches: Main query + individually extracted concepts
            search_strings = [(query_text, top_k * 2)]
            extracted_concepts = self.extract_entities(filter_query)
            if extracted_concepts:
                logger.debug(f"[KBPedia] Extracted {len(extracted_concepts)} concepts for independent vector search: {extracted_concepts}")
                concept_limit = max(2, top_k)
                for concept in extracted_concepts:
                    # Don't re-search the whole query if it somehow got returned
                    if concept.strip().lower() != query_text.strip().lower():
                        search_strings.append((concept.strip(), concept_limit))

            # Execute searches
            for text_to_embed, limit in search_strings:
                query_vector = embedder_fn(text_to_embed)
                sub_matches = self._vector_search(query_vector, limit=limit)
                matches.extend(sub_matches)

        except Exception as e:
            logger.debug(f"KBPedia embedding/search failed: {e}")

        seen_uris = set()
        candidates = []  # list of {name, uri, definition, triples}
        items = []       # final result items

        if not matches:
            logger.debug(f"KBPedia has no vector matches for '{query_text}'.")
        else:
            logger.debug(f"KBPedia matched {len(matches)} total concept(s) across {len(search_strings)} search(es).")

        for match in matches:
            uri = match["uri"]
            if uri in seen_uris:
                continue
            seen_uris.add(uri)

            # Build raw triples
            raw_triples = []
            if match["definition"]:
                raw_triples.append(f"definition: {match['definition'][:400]}")
            raw_triples.extend(self.get_neighborhood(uri))

            # Defensive filter: remove any triple that looks like an MCQ option
            mcq_pattern = re.compile(r'^[A-D][.):] ', re.IGNORECASE)
            raw_triples = [t for t in raw_triples if not mcq_pattern.match(t)]

            if not raw_triples:
                logger.debug(f"No raw triples for '{match['name']}' ({uri}), skipping.")
                continue

            # Buffer raw candidates for a single end-of-loop LLM pass
            candidates.append({
                "name": match["name"],
                "uri": uri,
                "definition": match.get("definition", ""),
                "triples": raw_triples,
            })

        # ── Augment with Wikidata ─────────────
        if self.enable_wikidata and candidates:
            logger.debug(f"[Wikidata] Concurrently augmenting {len(candidates)} candidates with Wikidata structural facts.")
            try:
                import asyncio
                from .wikidata_retriever import WikidataRetriever
                wd = WikidataRetriever()
                
                async def augment_candidate(c):
                    try:
                        res = await wd._search_entity_async(c["name"], limit=1)
                        if res:
                            qid = res[0]["qid"]
                            # Include a wider range of chemistry/physics/structural properties
                            extra = ["P527", "P279", "P31", "P361", "P1889", "P460", "P2579", "P921", "P366", "P1056", "P1542", "P1148", "P186", "P2054", "P2176"]
                            wd_facts = await wd._fetch_structural_facts_async(qid, extra_properties=extra)
                            if wd_facts:
                                # ── Dedicated Wikidata filter (per concept, synchronous) ────
                                filtered_wd_facts = self.filter_wikidata_triples(
                                    query=filter_query,
                                    concept_name=c["name"],
                                    wikidata_facts=wd_facts,
                                )
                                if filtered_wd_facts:
                                    c["triples"].extend([f"(Wikidata) {f}" for f in filtered_wd_facts])
                                else:
                                    logger.debug(f"[WikidataFilter] '{c['name']}': 0 wikidata facts kept — not merging.")
                    except Exception as e:
                        logger.debug(f"[Wikidata] Augmentation failed for {c['name']}: {e}")

                async def run_augmentation():
                    tasks = [augment_candidate(c) for c in candidates]
                    await asyncio.gather(*tasks)

                # Execute concurrent fetching inside sync context
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        task = asyncio.ensure_future(run_augmentation())
                        loop.run_until_complete(task)
                    else:
                        loop.run_until_complete(run_augmentation())
                except RuntimeError:
                    asyncio.run(run_augmentation())
                    
            except Exception as e:
                logger.debug(f"[Wikidata] Global fallback pipeline error: {e}")

        # ── LLM filtering logic ─────────────
        if candidates and self.llm:
            # Enforce coarse filter similar to pure GraphRAG's standard behavior
            filtered_candidates = self._filter_concepts_once(query_text, candidates, original_query=filter_query, status_callback=status_callback)
            logger.debug(f"End-filter kept {len(filtered_candidates)}/{len(candidates)} concepts.")
            filtered_concepts_to_use = filtered_candidates
            
            if filtered_concepts_to_use:
                # Prepare batch payload
                batch_data = [{"name": c["name"], "triples": c["triples"]} for c in filtered_concepts_to_use]
                logger.debug(f"Batch sending {len(batch_data)} concepts to LLM triple filter...")
                
                # Use unified batch filter
                batch_results = self.filter_triples_batch(query_text, batch_data, original_query=filter_query, status_callback=status_callback)
                
                # Reassign filtered triples back to the candidates
                for c in filtered_concepts_to_use:
                    selected = batch_results.get(c["name"], c["triples"])
                    logger.debug(f"Batch LLM filter kept {len(selected)}/{len(c['triples'])} triple(s) for '{c['name']}'")
                    c["triples"] = selected

                # Remove concepts where LLM filter kept 0 triples
                filtered_concepts_to_use = [c for c in filtered_concepts_to_use if c["triples"]]
        else:
            # Fallback if LLM is disabled: just use raw candidates
            filtered_concepts_to_use = candidates[:top_k]

        for c in filtered_concepts_to_use:
            # ── Final hard pass: deterministic junk removal on all triples ──
            c["triples"] = self._hard_filter_triples(c["triples"], c["name"])

        # Drop concepts that have zero triples after hard filtering
        filtered_concepts_to_use = [c for c in filtered_concepts_to_use if c["triples"]]

        for c in filtered_concepts_to_use:
            selected_triples = c["triples"]
            triples_text = "\n".join([f"- {t}" for t in selected_triples])
            content = f"KBPedia Concept: {c['name']}.\nRelevant Logical Facts:\n{triples_text}"
            items.append(RetrieverResultItem(
                content=content,
                metadata={"source": "KBPedia", "entity": c["name"],
                          "uri": c["uri"], "score": 1.0, "triples": selected_triples},
            ))

        logger.debug(f"KBPedia found {len(items)} grounded concept contexts.")
        return RetrieverResult(items=items, metadata={})
