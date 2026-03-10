"""
Grounded KBPedia Retriever — Neo4j Edition
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
from llm_config import log_llm_event, retry_with_exponential_backoff


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
            from .config import ENABLE_LLM_FILTERING
        except (ModuleNotFoundError, ImportError):
            try:
                from graphrag.config import ENABLE_LLM_FILTERING
            except ImportError:
                ENABLE_LLM_FILTERING = True

        # Nullify LLM if the global config toggle is disabled
        self.llm = llm if ENABLE_LLM_FILTERING else None
        
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
            print(f"DEBUG PROLOG-GRAPHRAG:Error verifying KBPedia vector index: {e}")
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
            print(f"DEBUG PROLOG-GRAPHRAG:KBPedia concept vector search error: {e}")
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
                    print(f"DEBUG PROLOG-GRAPHRAG:Entity extraction LLM returned no JSON array. Raw: {repr(res_text[:100])}")
            except Exception as e:
                print(f"DEBUG PROLOG-GRAPHRAG:KBPedia entity extraction LLM failed: {e}")

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
                print(f"DEBUG PROLOG-GRAPHRAG:KBPedia exact search failed for '{search_term}'. Trying longest-word fallback: '{longest_word}'", flush=True)
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
            print(f"DEBUG PROLOG-GRAPHRAG:KBPedia concept search error for '{safe_term}': {e}")
            return []

    def get_neighborhood(self, uri: str) -> List[str]:
        """Get the ontology neighborhood of a concept. Reduced strictly to immediate parent to minimize noise."""
        try:
            records, _, _ = self.driver.execute_query(
                """
                MATCH (n:KBPediaConcept {uri: $uri})
                OPTIONAL MATCH (n)-[:SUBCLASS_OF]->(ancestor:KBPediaConcept)
                RETURN collect(DISTINCT {name: ancestor.name})[0..2] AS ancestors
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
            return triples
        except Exception as e:
            print(f"DEBUG PROLOG-GRAPHRAG:KBPedia neighborhood error: {e}")
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
            print(f"DEBUG PROLOG-GRAPHRAG:Triple filter raw response for '{entity_label}': {repr(res[:200])}", flush=True)

            # Strip markdown code fences
            if "```json" in res:
                res = res.split("```json")[1].split("```")[0].strip()
            elif "```" in res:
                res = res.split("```")[1].split("```")[0].strip()

            # Guard: DebugOllamaLLM._clean_response_text() strips everything outside {},
            # so a JSON array comes back empty. Try to find brackets first.
            bracket_start = res.find('[')
            bracket_end = res.rfind(']')
            if bracket_start != -1 and bracket_end != -1:
                res = res[bracket_start:bracket_end + 1]
            elif not res:
                print(f"DEBUG PROLOG-GRAPHRAG:Triple filter got empty response for '{entity_label}'. Using all raw triples.", flush=True)
                return triples

            filtered = json.loads(res)
            if isinstance(filtered, list):
                return filtered
        except Exception as e:
            print(f"DEBUG PROLOG-GRAPHRAG:Triple filtering failed for '{entity_label}': {e}. Using all raw triples.", flush=True)

        return triples

    def filter_triples_batch(self, query: str, concepts_data: List[Dict[str, Any]], original_query: str = "") -> Dict[str, List[str]]:
        """
        Use LLM to keep only logically relevant triples for MULTIPLE concepts at once.
        concepts_data is a list of dicts: {"name": str, "triples": List[str]}
        Returns a dictionary mapping concept_name to a list of filtered triples.
        """
        if not self.llm or not concepts_data:
            return {c["name"]: c["triples"][:15] for c in concepts_data}

        filter_query = original_query if original_query else query

        # Build the payload for the prompt
        MAX_TRIPLES_PER_CONCEPT = 12
        concepts_text = ""
        for c in concepts_data:
            capped_triples = c["triples"][:MAX_TRIPLES_PER_CONCEPT]
            triples_text = "\n".join([f"  - {t}" for t in capped_triples])
            concepts_text += f"Concept: '{c['name']}'\nFacts:\n{triples_text}\n\n"

        prompt = f"""Task: Select ONLY the ontology facts that are directly useful for answering the user's question.

User Query: "{filter_query}"

{concepts_text}

FILTERING RULES:
1. KEEP a fact if it directly defines, characterises, or establishes a property/relationship that helps answer the question or distinguish between MCQ choices.
2. KEEP the core definition of a concept if it is relevant to the question's topic.
3. DROP any fact that is taxonomic boilerplate or structural metadata: counts of elements/properties ("has X elements"), abstract classifications ("subclass of: abstract object"), unrelated superclasses, or ontological hierarchy noise.
4. DROP facts about number of components, cardinality, or list sizes (e.g. "has 4 subclasses", "number of elements: 3") — these NEVER help answer factual questions.
5. DROP facts whose concept is clearly unrelated to the query topic or any MCQ choice.
6. Merge/group similar facts into a single entry where possible (e.g. "no air" and "no atmosphere" → keep just the more informative one).

Output format: A JSON dictionary where keys are the Concept names, and values are lists of fact strings.
Example:
{{
  "trench": ["definition: a long narrow excavation in the ground", "subclass of: topographical feature"],
  "temperature": []
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
                print(f"DEBUG PROLOG-GRAPHRAG:Batch triple filter raw response: {repr(safe_res)}...", flush=True)

                if "```json" in res:
                    res = res.split("```json")[1].split("```")[0].strip()
                elif "```" in res:
                    res = res.split("```")[1].split("```")[0].strip()

                bracket_start = res.find('{')
                bracket_end = res.rfind('}')
                if bracket_start != -1 and bracket_end != -1:
                    res = res[bracket_start:bracket_end + 1]
                elif not res:
                    print(f"DEBUG PROLOG-GRAPHRAG:Batch triple filter got empty response. Using all raw triples.", flush=True)
                    return result_map

                filtered = _safe_parse_json(res, expect=dict)
                if isinstance(filtered, dict):
                    for c in concepts_data:
                        name = c["name"]
                        if name in filtered and isinstance(filtered[name], list):
                            # Clean up formatting artifacts (like "- subclass of:" -> "subclass of:")
                            cleaned_triples = [t[2:].strip() if t.startswith("- ") else t.strip() for t in filtered[name]]
                            result_map[name] = cleaned_triples
                    return result_map # Return immediately on success
            except Exception as e:
                print(f"DEBUG PROLOG-GRAPHRAG:Batch triple filtering attempt {attempt + 1}/{max_retries} failed: {e}", flush=True)
                if attempt < max_retries - 1:
                    time.sleep(3)
                else:
                    print(f"DEBUG PROLOG-GRAPHRAG:All {max_retries} batch filtering attempts failed. Using all raw triples.", flush=True)

        return result_map



    def _filter_concepts_once(self, query_text: str, candidates: list, original_query: str = "") -> list:
        """
        Single LLM call to filter all candidates at once.
        `candidates` is a list of dicts: {name, uri, definition, triples}.
        `original_query` is the full user prompt including MCQ choices (when available).
        Returns a filtered list of dicts containing only relevant candidates.
        """
        if not self.llm or not candidates:
            return candidates

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

        prompt = f"""You are filtering knowledge graph concepts for a Prolog-based QA system.

User question: "{filter_query}"{mcq_hint}

Candidates (index: concept name: short definition):
{summary_text}

### Decision Criteria
You MUST select the minimal set of highly relevant concepts.

CRITICAL DEDUPLICATION RULES:
1. If multiple candidates represent the EXACT SAME real-world entity or idea (e.g., "cell membrane", "membrane (biological)", "membrane protein complex"), you MUST keep ONLY ONE (the most comprehensive/common). Reject the rest.
2. Never keep highly redundant concepts that just add noise.
3. Reject concepts that are clearly off-topic or coincidental word matches.

RELEVANCE RULES (Keep if true AND not redundant):
1. Its name or definition strictly relates to the question topic.
2. Its name or definition relates to ANY of the MCQ answer choices listed above.
3. It provides a fact crucial for the Prolog engine to derive an answer.

Return a JSON list of the RELEVANT indices (integers). Example: [0, 2, 4, 7]
Output ONLY the JSON list, nothing else.
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
                print(f"DEBUG PROLOG-GRAPHRAG:End-filter LLM kept indices: {indices} from {len(candidates)} candidates.", flush=True)
                return [candidates[i] for i in indices if isinstance(i, int) and 0 <= i < len(candidates)]
            except Exception as e:
                print(f"DEBUG PROLOG-GRAPHRAG:End-filter LLM attempt {attempt + 1}/{max_retries} failed: {e}.", flush=True)
                if attempt < max_retries - 1:
                    time.sleep(3)
                else:
                    print(f"DEBUG PROLOG-GRAPHRAG:All {max_retries} end-filter attempts failed. Returning all candidates.", flush=True)
        return candidates

    def search(self, query_text: str, top_k: int = 5, original_query: str = "", seeded_entities: List[str] = None) -> Any:
        from .retriever import RetrieverResult, RetrieverResultItem

        if not self._verify_index():
            return RetrieverResult(items=[], metadata={})

        # `original_query` = full user prompt (with MCQ choices) for LLM filtering.
        filter_query = original_query if original_query else query_text

        # ── Vector Search ───────────────────────────────────────────────────
        print(f"DEBUG PROLOG-GRAPHRAG:[KBPedia] Computing query embeddings to search KBPedia concepts...", flush=True)
        matches = []
        try:
            # Prepare the embedder function once
            embedder_fn = None
            if self.embedder:
                embedder_fn = lambda text: self.embedder.embed_query("query: " + text)
            else:
                from sentence_transformers import SentenceTransformer
                print("DEBUG PROLOG-GRAPHRAG:Pipeline embedder missing, falling back to local SentenceTransformer.", flush=True)
                temp_embedder = SentenceTransformer("all-MiniLM-L6-v2")
                embedder_fn = lambda text: temp_embedder.encode(text).tolist()

            # Schedule searches: Main query + individually extracted concepts
            search_strings = [(query_text, top_k * 2)]
            extracted_concepts = self.extract_entities(filter_query)
            if extracted_concepts:
                print(f"DEBUG PROLOG-GRAPHRAG:[KBPedia] Extracted {len(extracted_concepts)} concepts for independent vector search: {extracted_concepts}", flush=True)
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
            print(f"DEBUG PROLOG-GRAPHRAG:KBPedia embedding/search failed: {e}", flush=True)

        seen_uris = set()
        candidates = []  # list of {name, uri, definition, triples}
        items = []       # final result items

        if not matches:
            print(f"DEBUG PROLOG-GRAPHRAG:KBPedia has no vector matches for '{query_text}'.", flush=True)
        else:
            print(f"DEBUG PROLOG-GRAPHRAG:KBPedia matched {len(matches)} total concept(s) across {len(search_strings)} search(es).", flush=True)

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
                print(f"DEBUG PROLOG-GRAPHRAG:No raw triples for '{match['name']}' ({uri}), skipping.", flush=True)
                continue

            # Buffer raw candidates for a single end-of-loop LLM pass
            candidates.append({
                "name": match["name"],
                "uri": uri,
                "definition": match.get("definition", ""),
                "triples": raw_triples,
            })

        # ── LLM filtering logic ─────────────
        if candidates and self.llm:
            # Enforce coarse filter similar to pure GraphRAG's standard behavior
            filtered_candidates = self._filter_concepts_once(query_text, candidates, original_query=filter_query)
            print(f"DEBUG PROLOG-GRAPHRAG:End-filter kept {len(filtered_candidates)}/{len(candidates)} concepts.", flush=True)
            filtered_concepts_to_use = filtered_candidates
            
            if filtered_concepts_to_use:
                # Prepare batch payload
                batch_data = [{"name": c["name"], "triples": c["triples"]} for c in filtered_concepts_to_use]
                print(f"DEBUG PROLOG-GRAPHRAG:Batch sending {len(batch_data)} concepts to LLM triple filter...", flush=True)
                
                # Use unified batch filter
                batch_results = self.filter_triples_batch(query_text, batch_data, original_query=filter_query)
                
                # Reassign filtered triples back to the candidates
                for c in filtered_concepts_to_use:
                    selected = batch_results.get(c["name"], c["triples"])
                    print(f"DEBUG PROLOG-GRAPHRAG:Batch LLM filter kept {len(selected)}/{len(c['triples'])} triple(s) for '{c['name']}'", flush=True)
                    c["triples"] = selected

                # Remove concepts where LLM filter kept 0 triples
                filtered_concepts_to_use = [c for c in filtered_concepts_to_use if c["triples"]]
        else:
            # Fallback if LLM is disabled: just use raw candidates
            filtered_concepts_to_use = candidates[:top_k]

        for c in filtered_concepts_to_use:
            selected_triples = c["triples"]
            triples_text = "\n".join([f"  - {t}" for t in selected_triples])
            content = f"KBPedia Concept: {c['name']}.\nRelevant Logical Facts:\n{triples_text}"
            items.append(RetrieverResultItem(
                content=content,
                metadata={"source": "KBPedia", "entity": c["name"],
                          "uri": c["uri"], "score": 1.0, "triples": selected_triples},
            ))

        print(f"DEBUG PROLOG-GRAPHRAG:KBPedia found {len(items)} grounded concept contexts.", flush=True)
        return RetrieverResult(items=items, metadata={})
