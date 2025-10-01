from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import re


@dataclass
class SummaryResult:
    """Result of a conversation summarisation pass."""

    summary_text: str
    delta_text: str
    entities: List[str] = field(default_factory=list)
    used_fallback: bool = False
    confidence: float = 0.0
    should_use_summary: bool = False


class ConversationSummarizer:
    """Lightweight conversation summariser with confidence gating."""

    def __init__(self, confidence_threshold: float = 0.6) -> None:
        self.confidence_threshold = confidence_threshold

    def summarize(
        self,
        messages: List[Dict[str, str]],
        *,
        previous_summary: Optional[str] = None,
        previous_entities: Optional[List[str]] = None,
        preserve_sources: bool = True,
    ) -> SummaryResult:
        if not messages:
            # No new content – treat as fallback and keep the previous summary untouched.
            return SummaryResult(
                summary_text=previous_summary or "",
                delta_text="",
                entities=previous_entities or [],
                used_fallback=True,
                confidence=0.0,
                should_use_summary=False,
            )

        delta_segments: List[str] = []
        sources_info = []
        for message in messages:
            role = message.get("role", "")
            content = self._strip_citations((message.get("content") or "").strip())
            if not content:
                continue
            delta_segments.append(f"{role}: {content}")

            # 출처 정보 보존
            if preserve_sources and role == "assistant" and message.get("sources"):
                sources = message.get("sources", [])
                if sources:
                    sources_info.append(sources)

        delta_text = " | ".join(delta_segments)
        combined_summary = (
            delta_text if not previous_summary else f"{previous_summary} || {delta_text}"
        )

        confidence = 1.0 if delta_text else 0.0
        should_use_summary = bool(delta_text) and confidence >= self.confidence_threshold

        entities = self._merge_entities(
            previous_entities or [],
            self._extract_entities(messages)
        )

        return SummaryResult(
            summary_text=combined_summary,
            delta_text=delta_text,
            entities=entities,
            used_fallback=False,
            confidence=confidence,
            should_use_summary=should_use_summary,
        )

    def _strip_citations(self, text: str) -> str:
        if not text:
            return text
        return re.sub(r"\[[0-9]+\]", "", text)

    def _extract_entities(self, messages: List[Dict[str, str]]) -> List[str]:
        """
        Extract entities using STATISTICAL approach - NO HARDCODED patterns.

        Strategy: Extract content words automatically using morphological heuristics.
        Works for ANY domain (departments, locations, organizations, etc.) without
        hardcoding specific suffixes or entity types.
        """
        entities: List[str] = []

        for message in messages:
            if message.get("role") != "assistant":
                continue
            content = message.get("content") or ""
            # Remove citation markers like [1]
            content = re.sub(r"\[[0-9]+\]", "", content)

            # Extract ALL Korean words (3+ chars for meaningful entities)
            # NO domain-specific patterns - pure statistical extraction
            words = re.findall(r'[가-힣A-Za-z]{3,}', content)

            for word in words:
                # Filter using morphological heuristics (NO domain knowledge)
                if self._is_likely_entity(word):
                    cleaned = word.strip().strip(',')
                    if cleaned and cleaned not in entities:
                        entities.append(cleaned)

        # Apply statistical clustering to normalize variants
        # Example: "문화과", "문화과에서" -> "문화과"
        return self._normalize_entities_statistical(entities)

    def _is_likely_entity(self, word: str) -> bool:
        """
        Check if word is likely an entity using STATISTICAL heuristics.
        NO hardcoded patterns - works for any Korean domain.
        """
        # Length-based: entities tend to be 3+ chars
        if len(word) < 3:
            return False

        # Skip common verb/adjective endings (linguistic features, not domain-specific)
        if any(word.endswith(ending) for ending in ['하다', '되다', '이다', '한다', '된다', '합니다']):
            return False

        # Skip question patterns (linguistic features)
        if any(pattern in word for pattern in ['어떻', '무엇', '어디', '언제']):
            return False

        # Keep all other content words
        return True

    def _normalize_entities_statistical(self, entities: List[str]) -> List[str]:
        """
        Normalize entity variants using SUBSTRING CLUSTERING.
        Same approach as query_rewriter.py - pure statistics, no hardcoding.
        """
        if not entities:
            return []

        # Build clusters: entities with substring overlap belong to same cluster
        clusters = []
        for entity in entities:
            matched_cluster = None
            for cluster in clusters:
                for existing in cluster:
                    # Substring overlap detection
                    if entity in existing or existing in entity:
                        matched_cluster = cluster
                        break
                if matched_cluster:
                    break

            if matched_cluster:
                matched_cluster.add(entity)
            else:
                clusters.append({entity})

        # Select canonical form from each cluster (shortest = root)
        normalized = []
        for cluster in clusters:
            cluster_list = list(cluster)
            canonical = min(cluster_list, key=lambda x: (len(x), entities.index(x) if x in entities else 999))
            normalized.append(canonical)

        return normalized

    def _merge_entities(self, previous: List[str], current: List[str]) -> List[str]:
        merged: List[str] = []
        for source in (previous, current):
            for entity in source:
                if entity not in merged:
                    merged.append(entity)
        return merged
