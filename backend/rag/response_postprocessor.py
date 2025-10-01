"""Simple response postprocessor

Main entry point for all response corrections.
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class ResponsePostProcessor:
    """Simple postprocessor for RAG responses"""

    def __init__(self):
        self.enabled = False  # Disabled by default - causes too aggressive token removal
        self._token_pattern = re.compile(r'[가-힣A-Za-z]{2,}')

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

        # Align remaining tokens with evidence vocabulary
        text = self._harmonize_tokens(text, evidence_text)

        # Normalize whitespace produced by replacements
        text = re.sub(r'\s{2,}', ' ', text).strip()

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
        """Normalize entity-like tokens to match evidence terminology."""
        entity_pattern = r'[가-힣A-Za-z][가-힣A-Za-z\d]{2,}'
        response_entities = set(re.findall(entity_pattern, text))
        evidence_entities = set(re.findall(entity_pattern, evidence_text))

        if not response_entities or not evidence_entities:
            return text

        evidence_index: Dict[str, str] = {}
        for ent in evidence_entities:
            norm = self._normalize_entity(ent)
            if norm:
                evidence_index.setdefault(norm, ent)

        def replacement(match: re.Match) -> str:
            token = match.group(0)
            norm = self._normalize_entity(token)
            if norm in evidence_index:
                canonical = evidence_index[norm]
                if canonical != token:
                    logger.info("Canonicalizing entity '%s' → '%s'", token, canonical)
                return canonical

            # Fallback: find closest evidence entity
            best_token = None
            best_score = 0.0
            for evid_norm, evid_token in evidence_index.items():
                score = SequenceMatcher(None, norm, evid_norm).ratio()
                if score > best_score:
                    best_score = score
                    best_token = evid_token
                    if score >= 0.95:
                        break

            if best_token and best_score >= 0.85:
                logger.info("Replacing entity '%s' with '%s' (score %.2f)", token, best_token, best_score)
                return best_token

            logger.info("Removing unsupported entity '%s' (score %.2f)", token, best_score)
            return ''

        return re.sub(entity_pattern, replacement, text)

    def _harmonize_tokens(self, text: str, evidence_text: str) -> str:
        """Align general tokens with evidence terminology."""
        tokens = self._token_pattern.findall(text)
        if not tokens:
            return text

        evidence_tokens = self._token_pattern.findall(evidence_text)
        if not evidence_tokens:
            return text

        evidence_index: Dict[str, str] = {}
        for token in evidence_tokens:
            norm = self._normalize_text(token)
            if norm:
                evidence_index.setdefault(norm, token)

        def repl(match: re.Match) -> str:
            token = match.group(0)
            norm = self._normalize_text(token)
            canonical = evidence_index.get(norm)
            if canonical:
                return canonical

            best_token = None
            best_score = 0.0
            for evid_norm, evid_token in evidence_index.items():
                score = SequenceMatcher(None, norm, evid_norm).ratio()
                if score > best_score:
                    best_score = score
                    best_token = evid_token
                    if score >= 0.95:
                        break

            if best_token and best_score >= 0.85:
                logger.info("Token '%s' harmonized to '%s' (score %.2f)", token, best_token, best_score)
                return best_token

            logger.info("Dropping unsupported token '%s' (score %.2f)", token, best_score)
            return ''

        return self._token_pattern.sub(repl, text)

    def _normalize_entity(self, entity: str) -> str:
        """Normalize entity name for comparison"""
        if not entity:
            return ""

        # Convert to lowercase for case-insensitive comparison
        normalized = entity.lower()

        # Remove common punctuation
        normalized = re.sub(r'[.,!?;:]', '', normalized)

        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized

    def _normalize_text(self, text: str) -> str:
        """Normalize general text for comparison"""
        if not text:
            return ""

        # Convert to lowercase
        normalized = text.lower()

        # Remove punctuation
        normalized = re.sub(r'[^\w\s가-힣]', '', normalized)

        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()

        return normalized
