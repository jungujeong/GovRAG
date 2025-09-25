"""
Simple response postprocessor
Main entry point for all response corrections
"""

import logging
import re
from typing import Dict, List, Tuple, Optional

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

        return response

    def _clean_text(self, text: str, evidence_text: str) -> str:
        """Clean text by removing hallucinated content"""
        # Remove parenthetical additions not in evidence
        text = self._remove_fake_parentheticals(text, evidence_text)

        # Fix entity variations
        text = self._fix_entity_names(text, evidence_text)

        return text

    def _remove_fake_parentheticals(self, text: str, evidence_text: str) -> str:
        """Remove parenthetical content not in evidence"""
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
        from difflib import SequenceMatcher

        entity_pattern = r'[가-힣A-Za-z][가-힣A-Za-z\d]{2,}'
        text_entities = set(re.findall(entity_pattern, text))
        evidence_entities = set(re.findall(entity_pattern, evidence_text))

        normalized_evidence = {
            self._normalize_entity(e): e for e in evidence_entities
        }

        for entity in text_entities:
            norm_entity = self._normalize_entity(entity)
            if not norm_entity:
                # Remove non-Korean entities
                text = re.sub(rf'\b{re.escape(entity)}\b', '', text)
                continue

            if norm_entity in normalized_evidence:
                canonical = normalized_evidence[norm_entity]
                if entity != canonical:
                    logger.info("Canonicalizing entity '%s' → '%s'", entity, canonical)
                    text = re.sub(rf'\b{re.escape(entity)}\b', canonical, text)
                continue

            # Find closest match
            best_match = None
            best_score = 0.0
            for evid_norm, evid_entity in normalized_evidence.items():
                if not evid_norm:
                    continue
                score = SequenceMatcher(None, norm_entity, evid_norm).ratio()
                if score > best_score:
                    best_score = score
                    best_match = evid_entity

            if best_match and best_score >= 0.8:
                logger.info("Replacing entity '%s' with '%s' (score %.2f)", entity, best_match, best_score)
                text = re.sub(rf'\b{re.escape(entity)}\b', best_match, text)
            else:
                logger.info("Removing unsupported entity '%s' (score %.2f)", entity, best_score)
                text = re.sub(rf'\b{re.escape(entity)}\b', '', text)

        return text

    def _filter_sentences_by_evidence(self, text: str, evidence_text: str) -> str:
        if not text:
            return text

        evidence_norm = self._normalize_text(evidence_text)
        if not evidence_norm:
            return text

        lines = text.split('\n')
        filtered: List[str] = []
        kept_any = False

        for line in lines:
            stripped = line.strip()
            if not stripped:
                filtered.append(line)
                continue

            coverage = self._line_coverage(stripped, evidence_norm)
            if coverage >= 0.35 or not kept_any:
                filtered.append(line)
                if stripped:
                    kept_any = True
            else:
                logger.info("Dropping low-evidence sentence: '%s' (coverage=%.2f)", stripped[:80], coverage)

        return '\n'.join(filtered)

    def _line_coverage(self, line: str, evidence_norm: str) -> float:
        tokens = re.findall(r'[가-힣A-Za-z]{2,}', line)
        if not tokens:
            return 0.0
        total = len(tokens)
        hits = 0
        for token in tokens:
            token_norm = self._normalize_text(token)
            if token_norm and token_norm in evidence_norm:
                hits += 1
        return hits / total if total else 0.0

    def _normalize_text(self, text: str) -> str:
        return re.sub(r'\s+', ' ', text).lower().strip()

    def _normalize_entity(self, entity: str) -> str:
        return re.sub(r'[^가-힣]', '', entity)
