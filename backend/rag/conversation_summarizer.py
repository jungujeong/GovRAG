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
        entities: List[str] = []
        # 부서명 패턴 + 주요 개체명 패턴
        dept_pattern = re.compile(r"([가-힣A-Za-z]+(?:과|부|국|처|실|단|팀|센터))")
        entity_pattern = re.compile(r"([가-힣]{2,}(?:예술촌|문화마을|산업단지|공단|상권|함박천))")

        for message in messages:
            if message.get("role") != "assistant":
                continue
            content = message.get("content") or ""
            # Remove citation markers like [1]
            content = re.sub(r"\[[0-9]+\]", "", content)

            # 부서명 추출
            for match in dept_pattern.findall(content):
                cleaned = match.strip().strip(',')
                if cleaned and cleaned not in entities:
                    entities.append(cleaned)

            # 주요 개체명 추출
            for match in entity_pattern.findall(content):
                cleaned = match.strip().strip(',')
                if cleaned and cleaned not in entities:
                    entities.append(cleaned)

        return entities

    def _merge_entities(self, previous: List[str], current: List[str]) -> List[str]:
        merged: List[str] = []
        for source in (previous, current):
            for entity in source:
                if entity not in merged:
                    merged.append(entity)
        return merged
