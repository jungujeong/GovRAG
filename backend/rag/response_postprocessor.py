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
        self.enabled = False  # DISABLED: Too aggressive - destroys valid LLM responses
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
        """
        Normalize entity using STATISTICAL suffix trimming - NO HARDCODING.

        Strategy: Iteratively trim 1-2 characters from end and check if
        shorter form is more "canonical" (has higher character diversity).

        This works for ANY Korean dialect without hardcoded particle lists.
        """
        if not entity:
            return ""

        # Start with the entity as-is
        normalized = entity.strip()

        # Statistical suffix trimming: Try removing 1-2 chars at a time
        # Keep the shortest form that maintains high character diversity
        best_form = normalized
        best_diversity = self._calculate_diversity(normalized)

        # Try trimming 1-2 characters iteratively
        for trim_length in [1, 2]:
            if len(normalized) > trim_length + 1:  # Keep at least 2 chars
                candidate = normalized[:-trim_length]

                # Calculate character diversity of candidate
                candidate_diversity = self._calculate_diversity(candidate)

                # If candidate has higher or equal diversity, it's likely the root form
                # (particles typically reduce diversity by adding common chars)
                if candidate_diversity >= best_diversity:
                    best_form = candidate
                    best_diversity = candidate_diversity

        return best_form.lower().strip()

    def _calculate_diversity(self, text: str) -> float:
        """
        Calculate character diversity (unique chars / total chars).
        Higher diversity = more information content = more likely root form.
        """
        if not text:
            return 0.0
        return len(set(text)) / len(text)

    def _normalize_text(self, text: str) -> str:
        """Normalize text by converting to lowercase and stripping whitespace"""
        if not text:
            return ""
        return text.lower().strip()
