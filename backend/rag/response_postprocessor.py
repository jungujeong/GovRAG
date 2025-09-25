"""
Simple response postprocessor
Main entry point for all response corrections
"""

import logging
from typing import Dict, List, Tuple, Optional, Set

logger = logging.getLogger(__name__)


class ResponsePostProcessor:
    """Simple postprocessor for RAG responses"""

    def __init__(self):
        self.enabled = True

    def process(
        self,
        response: Dict,
        evidences: List[Dict],
        query: Optional[str] = None
    ) -> Dict:
        """
        Process and clean response based on evidences

        Simple approach: Remove anything not in evidence
        """
        if not self.enabled:
            return response

        # Build evidence vocabulary
        evidence_text = " ".join([e.get("text", "") for e in evidences])
        evidence_words = set(evidence_text.split())

        # Process answer
        if "answer" in response:
            response["answer"] = self._clean_text(response["answer"], evidence_text)

        # Process key facts
        if "key_facts" in response:
            response["key_facts"] = [
                self._clean_text(fact, evidence_text)
                for fact in response["key_facts"]
            ]

        # Process details
        if "details" in response:
        response["details"] = self._clean_text(response["details"], evidence_text)

        # Apply structured summaries when beneficial
        self._maybe_apply_department_summary(response, evidences, query)

        return response

    def _clean_text(self, text: str, evidence_text: str) -> str:
        """Clean text by removing hallucinated content"""
        import re

        # Remove parenthetical additions not in evidence
        text = self._remove_fake_parentheticals(text, evidence_text)

        # Fix entity variations
        text = self._fix_entity_names(text, evidence_text)

        return text

    # ------------------------------------------------------------------
    # Structured summaries
    # ------------------------------------------------------------------
    def _maybe_apply_department_summary(
        self,
        response: Dict,
        evidences: List[Dict],
        query: Optional[str]
    ) -> None:
        if not query:
            return
        lower_query = query.lower()
        trigger_keywords = ("부서", "담당", "department")
        if not any(keyword in lower_query for keyword in trigger_keywords):
            return

        dept_map = self._extract_departments_by_doc(evidences)
        if not dept_map:
            return

        citation_lookup: Dict[str, int] = {}
        for source in response.get("sources", []) or []:
            doc_id = source.get("doc_id")
            if not doc_id:
                continue
            idx = source.get("display_index") or source.get("index")
            if not idx:
                continue
            citation_lookup.setdefault(doc_id, idx)

        summary_lines: List[str] = []
        for doc_id, departments in dept_map.items():
            if not departments:
                continue
            display_id = self._prettify_doc_id(doc_id)
            dept_list = ", ".join(sorted(departments))
            citation = citation_lookup.get(doc_id)
            if citation:
                summary_lines.append(f"{display_id}: {dept_list} [{citation}]")
            else:
                summary_lines.append(f"{display_id}: {dept_list}")

        if not summary_lines:
            return

        response["key_facts"] = summary_lines
        response.setdefault("metadata", {})
        response["metadata"]["structured_summary"] = "departments"
        if not response.get("answer"):
            response["answer"] = "요청하신 담당 부서 정보는 다음과 같습니다."

    def _extract_departments_by_doc(self, evidences: List[Dict]) -> Dict[str, Set[str]]:
        dept_pattern = re.compile(r'([가-힣]{2,}(?:과|부|처|실|단|국|팀|센터|소|본부))')
        result: Dict[str, Set[str]] = {}
        for evidence in evidences or []:
            doc_id = evidence.get("doc_id")
            if not doc_id:
                continue
            text = evidence.get("text") or ""
            matches = dept_pattern.findall(text)
            if not matches:
                continue
            normalized_doc = self._normalize_doc_id(doc_id)
            bucket = result.setdefault(normalized_doc, set())
            for match in matches:
                cleaned = match.strip()
                if cleaned:
                    bucket.add(cleaned)
        return result

    def _normalize_doc_id(self, doc_id: str) -> str:
        doc_id = doc_id.strip()
        if not doc_id:
            return doc_id
        return doc_id

    def _prettify_doc_id(self, doc_id: str) -> str:
        base = doc_id.rsplit('/', 1)[-1]
        if base.lower().endswith('.pdf'):
            base = base[:-4]
        return base

    def _remove_fake_parentheticals(self, text: str, evidence_text: str) -> str:
        """Remove parenthetical content not in evidence"""
        import re

        # More robust pattern for Korean entities with parentheses
        pattern = r'([가-힣]+(?:[가-힣\d]*)?)\s*\(([^)]+)\)'

        for match in re.finditer(pattern, text):
            full_match = match.group(0)
            base_entity = match.group(1)
            paren_content = match.group(2)

            # Check if this exact pattern exists in evidence
            if full_match not in evidence_text:
                # Check if base entity exists in evidence
                if base_entity in evidence_text:
                    # Remove the parenthetical part
                    text = text.replace(full_match, base_entity)
                    logger.info(f"Removed fake parenthetical: {full_match} → {base_entity}")
                # Check if the parenthetical content is the correct entity
                elif paren_content in evidence_text:
                    # Use the parenthetical content instead
                    text = text.replace(full_match, paren_content)
                    logger.info(f"Used parenthetical as correct: {full_match} → {paren_content}")

        return text

    def _fix_entity_names(self, text: str, evidence_text: str) -> str:
        """Fix entity name variations"""
        import re
        from difflib import SequenceMatcher

        # Extract entities from both texts (improved pattern)
        entity_pattern = r'[가-힣]{3,}(?:[가-힣\d]+)?'
        text_entities = re.findall(entity_pattern, text)
        evidence_entities = re.findall(entity_pattern, evidence_text)

        # Build unique sets
        unique_text_entities = set(text_entities)
        unique_evidence_entities = set(evidence_entities)

        # Build replacement map
        replacements = {}

        for text_entity in unique_text_entities:
            if text_entity not in unique_evidence_entities:
                # Find best match
                best_match = None
                best_score = 0

                for evid_entity in unique_evidence_entities:
                    # Skip if too different in length
                    if abs(len(text_entity) - len(evid_entity)) > 3:
                        continue

                    # Calculate similarity
                    sim = SequenceMatcher(None, text_entity, evid_entity).ratio()

                    # Check for common prefix (important for Korean compounds)
                    common_prefix_len = 0
                    for i, (c1, c2) in enumerate(zip(text_entity, evid_entity)):
                        if c1 == c2:
                            common_prefix_len += 1
                        else:
                            break

                    # Weighted score
                    if common_prefix_len >= 2:  # At least 2 chars in common at start
                        weighted_sim = sim * 0.7 + (common_prefix_len / len(text_entity)) * 0.3
                    else:
                        weighted_sim = sim

                    # If very similar but not exact
                    if 0.7 < weighted_sim < 1.0 and weighted_sim > best_score:
                        best_score = weighted_sim
                        best_match = evid_entity

                if best_match and best_score > 0.75:
                    replacements[text_entity] = best_match
                    logger.info(f"Will replace '{text_entity}' with '{best_match}' (score: {best_score:.2f})")

        # Apply replacements (careful with word boundaries)
        for old, new in replacements.items():
            # Use lookahead/lookbehind for Korean word boundaries
            pattern = f'(?<![가-힣]){re.escape(old)}(?![가-힣])'
            text = re.sub(pattern, new, text)
            logger.info(f"Applied replacement: {old} → {new}")

        return text
