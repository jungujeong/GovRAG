"""
Real-time response correction during streaming
Catches and fixes hallucinations as they appear
"""

import re
import logging
from typing import Dict, List, Optional, Set
from collections import deque

logger = logging.getLogger(__name__)


class RealTimeCorrector:
    """Corrects LLM output in real-time during streaming"""

    def __init__(self, evidences: List[Dict]):
        """Initialize with evidence documents"""
        self.evidence_text = " ".join([e.get("text", "") for e in evidences])
        self.evidence_entities = self._extract_all_entities()
        self.correction_map = {}
        self.buffer = deque(maxlen=100)  # Rolling buffer for context

    def _extract_all_entities(self) -> Set[str]:
        """Extract all entities from evidence"""
        # Extract Korean compound nouns/entities
        pattern = r'[가-힣]{2,}(?:[가-힣\d]+)?'
        entities = set(re.findall(pattern, self.evidence_text))

        # Filter to meaningful entities (3+ chars)
        entities = {e for e in entities if len(e) >= 3}

        logger.info(f"Extracted {len(entities)} entities from evidence")
        return entities

    def process_token(self, token: str) -> str:
        """Process a single token/chunk and correct if needed"""
        # Add to buffer
        self.buffer.append(token)

        # Get current context (last N tokens)
        context = ''.join(self.buffer)

        # Check for patterns that need correction
        corrected_token = self._correct_token(token, context)

        return corrected_token

    def _correct_token(self, token: str, context: str) -> str:
        """Apply corrections to token based on context"""

        # 1. Check if we're in the middle of an entity
        current_entity = self._extract_current_entity(context)

        if current_entity:
            # Check if this entity is being modified incorrectly
            if self._is_entity_modification(current_entity):
                # Return original entity from evidence
                if current_entity in self.correction_map:
                    return self.correction_map[current_entity]

        # 2. Check for parenthetical additions
        if '(' in token:
            return self._handle_parenthesis(token, context)

        # 3. Check for suspicious variations
        return self._check_variations(token, context)

    def _extract_current_entity(self, context: str) -> Optional[str]:
        """Extract the entity being currently written"""
        # Look for Korean entity at the end of context
        pattern = r'([가-힣]{2,}(?:[가-힣\d]+)?)$'
        match = re.search(pattern, context)

        if match:
            return match.group(1)
        return None

    def _is_entity_modification(self, entity: str) -> bool:
        """Check if entity is being modified from original"""
        if len(entity) < 3:
            return False

        # Check if this looks like a variation of something in evidence
        for evidence_entity in self.evidence_entities:
            # Check prefix match
            if evidence_entity.startswith(entity[:2]):
                # This might be building toward a different entity
                if entity != evidence_entity[:len(entity)]:
                    # Store correction
                    self.correction_map[entity] = evidence_entity
                    return True

        return False

    def _handle_parenthesis(self, token: str, context: str) -> str:
        """Handle parenthetical additions"""
        # Check if we're adding a parenthetical to an entity
        pattern = r'([가-힣]{3,})\s*\($'
        match = re.search(pattern, context + token)

        if match:
            entity = match.group(1)

            # Check if this entity+parenthetical exists in evidence
            evidence_pattern = entity + r'\s*\([^)]+\)'
            if not re.search(evidence_pattern, self.evidence_text):
                # Block the parenthetical addition
                logger.warning(f"Blocking parenthetical addition for '{entity}'")
                return ''  # Return empty to skip this token

        return token

    def _check_variations(self, token: str, context: str) -> str:
        """Check for entity variations and correct them"""
        # Build the current word
        current_word = self._get_current_word(context + token)

        if current_word and len(current_word) >= 4:
            # Check if this is a variation of something in evidence
            best_match = self._find_similar_entity(current_word)

            if best_match and best_match != current_word:
                # Calculate what to return to correct the word
                logger.info(f"Correcting '{current_word}' to '{best_match}'")

                # Return the corrected portion
                return best_match[len(context.split()[-1]):]

        return token

    def _get_current_word(self, text: str) -> Optional[str]:
        """Get the current word being built"""
        words = re.findall(r'[가-힣]+', text)
        if words:
            return words[-1]
        return None

    def _find_similar_entity(self, word: str) -> Optional[str]:
        """Find similar entity in evidence"""
        from difflib import SequenceMatcher

        best_match = None
        best_score = 0

        for entity in self.evidence_entities:
            # Skip if too different in length
            if abs(len(word) - len(entity)) > 2:
                continue

            # Calculate similarity
            similarity = SequenceMatcher(None, word, entity).ratio()

            # High similarity but not exact = potential hallucination
            if 0.7 < similarity < 1.0:
                if similarity > best_score:
                    best_score = similarity
                    best_match = entity

        return best_match


class TokenBuffer:
    """Buffer for managing token corrections"""

    def __init__(self, max_size: int = 50):
        self.tokens = deque(maxlen=max_size)
        self.corrections = {}

    def add(self, token: str, corrected: str = None):
        """Add token and its correction if any"""
        self.tokens.append(token)
        if corrected and corrected != token:
            self.corrections[len(self.tokens) - 1] = corrected

    def get_context(self, n: int = 10) -> str:
        """Get last n tokens as context"""
        recent = list(self.tokens)[-n:]
        return ''.join(recent)

    def apply_corrections(self) -> str:
        """Get the corrected full text"""
        result = []
        for i, token in enumerate(self.tokens):
            if i in self.corrections:
                result.append(self.corrections[i])
            else:
                result.append(token)
        return ''.join(result)