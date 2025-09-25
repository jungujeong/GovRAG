"""
Response validation and correction pipeline
Validates and corrects LLM responses without hardcoded patterns
"""

import re
import logging
from typing import Dict, List, Tuple, Optional
from difflib import SequenceMatcher
import Levenshtein

logger = logging.getLogger(__name__)


class ResponseValidator:
    """Validates and corrects LLM responses based on evidence"""

    def __init__(self):
        self.min_similarity_threshold = 0.85
        self.entity_length_threshold = 3

    def validate_and_correct(
        self,
        response: Dict,
        evidences: List[Dict]
    ) -> Tuple[Dict, List[str]]:
        """
        Validate response and auto-correct issues

        Returns:
            Tuple of (corrected_response, issues_found)
        """
        issues = []

        # Extract evidence text for validation
        evidence_text = " ".join([e.get("text", "") for e in evidences])

        # Process each component
        if "answer" in response:
            response["answer"], answer_issues = self._validate_text(
                response["answer"],
                evidence_text,
                "answer"
            )
            issues.extend(answer_issues)

        if "key_facts" in response:
            corrected_facts = []
            for fact in response.get("key_facts", []):
                corrected_fact, fact_issues = self._validate_text(
                    fact,
                    evidence_text,
                    "key_fact"
                )
                corrected_facts.append(corrected_fact)
                issues.extend(fact_issues)
            response["key_facts"] = corrected_facts

        if "details" in response:
            response["details"], detail_issues = self._validate_text(
                response["details"],
                evidence_text,
                "details"
            )
            issues.extend(detail_issues)

        return response, issues

    def _validate_text(
        self,
        text: str,
        evidence_text: str,
        text_type: str
    ) -> Tuple[str, List[str]]:
        """Validate and correct a text segment"""
        issues = []
        corrected_text = text

        # 1. Check for entities with parenthetical additions
        corrected_text, paren_issues = self._fix_parenthetical_additions(
            corrected_text,
            evidence_text
        )
        issues.extend(paren_issues)

        # 2. Check for entity variations
        corrected_text, entity_issues = self._fix_entity_variations(
            corrected_text,
            evidence_text
        )
        issues.extend(entity_issues)

        # 3. Check for fabricated content
        fabrication_issues = self._detect_fabrication(
            corrected_text,
            evidence_text
        )
        issues.extend(fabrication_issues)

        return corrected_text, issues

    def _fix_parenthetical_additions(
        self,
        text: str,
        evidence_text: str
    ) -> Tuple[str, List[str]]:
        """Remove parenthetical additions not in evidence"""
        issues = []

        # Find all entities with parentheses in response
        pattern = r'([가-힣]+[가-힣\d]*)\s*\(([^)]+)\)'
        matches = re.finditer(pattern, text)

        corrections = []
        for match in matches:
            entity = match.group(1)
            parenthetical = match.group(2)
            full_match = match.group(0)

            # Check if this exact pattern exists in evidence
            if full_match not in evidence_text:
                # Check if entity exists without parentheses
                if entity in evidence_text:
                    # Entity exists but parenthetical was added
                    corrections.append((full_match, entity))
                    issues.append(
                        f"Removed added explanation '({parenthetical})' for '{entity}'"
                    )

        # Apply corrections
        for original, replacement in corrections:
            text = text.replace(original, replacement)

        return text, issues

    def _fix_entity_variations(
        self,
        text: str,
        evidence_text: str
    ) -> Tuple[str, List[str]]:
        """Fix entity name variations using fuzzy matching"""
        issues = []

        # Extract potential entities (Korean compound words)
        text_entities = self._extract_entities(text)
        evidence_entities = self._extract_entities(evidence_text)

        corrections = {}

        for text_entity in text_entities:
            if text_entity not in evidence_entities:
                # Find best match in evidence
                best_match = self._find_best_match(
                    text_entity,
                    evidence_entities
                )

                if best_match:
                    similarity = SequenceMatcher(
                        None,
                        text_entity,
                        best_match
                    ).ratio()

                    if similarity > self.min_similarity_threshold:
                        corrections[text_entity] = best_match
                        issues.append(
                            f"Corrected '{text_entity}' to '{best_match}'"
                        )

        # Apply corrections
        for original, replacement in corrections.items():
            # Use word boundaries to avoid partial replacements
            pattern = r'\b' + re.escape(original) + r'\b'
            text = re.sub(pattern, replacement, text)

        return text, issues

    def _extract_entities(self, text: str) -> List[str]:
        """Extract potential entity names from text"""
        # Extract words containing Korean and alpha characters (3+ chars)
        pattern = r'[가-힣A-Za-z][가-힣A-Za-z\d]{2,}'
        entities = re.findall(pattern, text)

        # Filter out common words (would need a proper Korean stopword list)
        # For now, just filter by length
        entities = [
            e for e in entities
            if len(e) >= self.entity_length_threshold
        ]

        return list(set(entities))

    def _find_best_match(
        self,
        target: str,
        candidates: List[str]
    ) -> Optional[str]:
        """Find best matching entity using multiple similarity metrics"""
        if not candidates:
            return None

        best_match = None
        best_score = 0

        for candidate in candidates:
            # Skip if lengths are too different
            if abs(len(target) - len(candidate)) > 3:
                continue

            # Combine multiple similarity metrics

            # 1. Sequence similarity
            seq_sim = SequenceMatcher(None, target, candidate).ratio()

            # 2. Levenshtein distance (normalized)
            lev_dist = Levenshtein.distance(target, candidate)
            lev_sim = 1 - (lev_dist / max(len(target), len(candidate)))

            # 3. Prefix similarity (important for Korean compounds)
            prefix_len = len(self._common_prefix(target, candidate))
            prefix_sim = prefix_len / min(len(target), len(candidate))

            # Weighted combination
            combined_score = (
                seq_sim * 0.4 +
                lev_sim * 0.4 +
                prefix_sim * 0.2
            )

            if combined_score > best_score:
                best_score = combined_score
                best_match = candidate

        # Only return if similarity is high enough
        if best_score > self.min_similarity_threshold:
            return best_match

        return None

    def _common_prefix(self, s1: str, s2: str) -> str:
        """Find common prefix of two strings"""
        for i, (c1, c2) in enumerate(zip(s1, s2)):
            if c1 != c2:
                return s1[:i]
        return s1[:min(len(s1), len(s2))]

    def _detect_fabrication(
        self,
        text: str,
        evidence_text: str
    ) -> List[str]:
        """Detect potential fabricated content"""
        issues = []

        # Check for sentences not grounded in evidence
        sentences = self._split_sentences(text)

        for sentence in sentences:
            # Skip very short sentences
            if len(sentence) < 10:
                continue

            # Check if key content words appear in evidence
            content_words = self._extract_content_words(sentence)

            if content_words:
                found_count = sum(
                    1 for word in content_words
                    if word in evidence_text
                )

                coverage = found_count / len(content_words)

                if coverage < 0.3:  # Less than 30% of content words found
                    issues.append(
                        f"Low evidence grounding for: {sentence[:50]}..."
                    )

        return issues

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences (Korean-aware)"""
        # Simple Korean sentence splitting
        sentences = re.split(r'[.!?]\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_content_words(self, sentence: str) -> List[str]:
        """Extract content-bearing words from sentence"""
        # Extract Korean words (2+ characters)
        words = re.findall(r'[가-힣]{2,}', sentence)

        # Filter out very common words (simplified)
        # In production, use proper Korean stopword list
        common_words = {
            '있습니다', '있으며', '되어', '하고', '있는',
            '대한', '대해', '위한', '통해', '따라'
        }

        content_words = [
            w for w in words
            if w not in common_words and len(w) >= 2
        ]

        return content_words


class StreamingValidator:
    """Validator for streaming responses"""

    def __init__(self, validator: ResponseValidator):
        self.validator = validator
        self.buffer = ""
        self.evidence_text = ""

    def set_evidence(self, evidences: List[Dict]):
        """Set evidence for validation"""
        self.evidence_text = " ".join([e.get("text", "") for e in evidences])

    def validate_chunk(self, chunk: str) -> str:
        """Validate and correct a streaming chunk"""
        # Add to buffer
        self.buffer += chunk

        # Check if we have a complete entity with parentheses
        pattern = r'([가-힣]+[가-힣\d]*)\s*\([^)]*\)'
        match = re.search(pattern, self.buffer)

        if match:
            # Validate this entity
            corrected, _ = self.validator._fix_parenthetical_additions(
                match.group(0),
                self.evidence_text
            )

            # If correction needed, modify chunk
            if corrected != match.group(0):
                # Replace in current chunk if possible
                if match.group(0) in chunk:
                    chunk = chunk.replace(match.group(0), corrected)

            # Clear processed part from buffer
            self.buffer = self.buffer[match.end():]

        return chunk
