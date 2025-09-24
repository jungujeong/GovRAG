"""Align model responses with retrieved evidences to improve literal accuracy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import logging
import re

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


@dataclass
class GroundingMatch:
    segment: str
    corrected: str
    score: float
    doc_id: Optional[str]
    page: Optional[int]
    chunk_id: Optional[str]
    type: str
    index: int
    citations: List[str]
    matched_text: Optional[str]
    adjusted: bool = False


class ResponseGrounder:
    """Align generated sentences to evidence snippets and optionally snap them."""

    def __init__(self, match_threshold: int = 55, snap_threshold: int = 86) -> None:
        self.match_threshold = match_threshold
        self.snap_threshold = snap_threshold
        self._citation_pattern = re.compile(r"\[(\d+)\]")
        self._whitespace_pattern = re.compile(r"\s+")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def ground(self, response: Dict[str, Any], evidences: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        if not response or not evidences:
            return response

        evidence_units = self._prepare_evidence_units(evidences)
        if not evidence_units:
            return response

        grounding_entries: List[GroundingMatch] = []

        # Answer paragraphs
        answer = response.get("answer")
        if isinstance(answer, str) and answer.strip():
            new_answer, matches = self._ground_text(answer, "answer", evidence_units)
            response["answer"] = new_answer
            grounding_entries.extend(matches)

        # Key facts
        key_facts = response.get("key_facts")
        if isinstance(key_facts, list) and key_facts:
            new_facts: List[str] = []
            for idx, fact in enumerate(key_facts):
                if not isinstance(fact, str) or not fact.strip():
                    new_facts.append(fact)
                    continue
                corrected, match = self._ground_line(fact, "key_fact", idx, evidence_units)
                new_facts.append(corrected)
                grounding_entries.append(match)
            response["key_facts"] = new_facts

        # Details
        details = response.get("details")
        if isinstance(details, str) and details.strip():
            new_details, matches = self._ground_text(details, "details", evidence_units)
            response["details"] = new_details
            grounding_entries.extend(matches)

        # Persist grounding metadata in serialisable form
        response["grounding"] = [
            {
                "segment": entry.segment,
                "corrected": entry.corrected,
                "score": entry.score,
                "doc_id": entry.doc_id,
                "page": entry.page,
                "chunk_id": entry.chunk_id,
                "type": entry.type,
                "index": entry.index,
                "citations": entry.citations,
                "matched_text": entry.matched_text,
                "adjusted": entry.adjusted,
            }
            for entry in grounding_entries
        ]

        return response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ground_text(
        self,
        text: str,
        segment_type: str,
        evidence_units: Sequence[Dict[str, Any]],
    ) -> Tuple[str, List[GroundingMatch]]:
        lines = text.splitlines()
        matches: List[GroundingMatch] = []
        grounded_lines: List[str] = []
        segment_index = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                grounded_lines.append(line)
                continue
            corrected, match = self._ground_line(
                stripped,
                segment_type,
                segment_index,
                evidence_units,
                original_line=line,
            )
            prefix_len = len(line) - len(line.lstrip(" \t"))
            prefix = line[:prefix_len]
            grounded_lines.append(prefix + corrected)
            matches.append(match)
            segment_index += 1

        new_text = "\n".join(grounded_lines).strip()
        return new_text, matches

    def _ground_line(
        self,
        line: str,
        segment_type: str,
        index: int,
        evidence_units: Sequence[Dict[str, Any]],
        original_line: Optional[str] = None,
    ) -> Tuple[str, GroundingMatch]:
        citations = self._citation_pattern.findall(line)
        clean_line = self._citation_pattern.sub("", line).strip()

        best_unit: Optional[Dict[str, Any]] = None
        best_score = -1

        for unit in evidence_units:
            unit_text = unit.get("text")
            if not unit_text:
                continue
            score = fuzz.token_set_ratio(clean_line, unit_text)
            if score > best_score:
                best_score = score
                best_unit = unit

        corrected_line = line
        matched_text: Optional[str] = None
        adjusted = False

        if best_unit and best_score >= self.match_threshold:
            matched_text = best_unit.get("text", "")
            if matched_text:
                candidate = matched_text.strip()
                if best_score >= self.snap_threshold and self._should_snap(clean_line, candidate):
                    corrected_line = self._reapply_format(candidate, citations, original_line or line)
                    adjusted = corrected_line.strip() != line.strip()
        else:
            best_unit = None

        match = GroundingMatch(
            segment=line,
            corrected=corrected_line,
            score=max(best_score, 0) / 100.0,
            doc_id=best_unit.get("doc_id") if best_unit else None,
            page=best_unit.get("page") if best_unit else None,
            chunk_id=best_unit.get("chunk_id") if best_unit else None,
            type=segment_type,
            index=index,
            citations=[f"[{c}]" for c in citations],
            matched_text=matched_text,
            adjusted=adjusted,
        )

        return corrected_line, match

    def _reapply_format(self, text: str, citations: Sequence[str], original_line: str) -> str:
        prefix_len = len(original_line) - len(original_line.lstrip(" \t"))
        prefix = original_line[:prefix_len]
        suffix = ""
        if citations:
            suffix = " " + " ".join(f"[{c}]" for c in citations)
        compact = self._whitespace_pattern.sub(" ", text).strip()
        return f"{prefix}{compact}{suffix}".rstrip()

    def _should_snap(self, original: str, candidate: str) -> bool:
        if not original:
            return False
        # Avoid snapping if the candidate is extremely short compared to original
        if len(candidate.split()) < max(2, len(original.split()) // 3):
            return False
        # Favour snapping when wording meaningfully differs
        direct_ratio = fuzz.ratio(original, candidate)
        return direct_ratio < 96

    def _prepare_evidence_units(self, evidences: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        units: List[Dict[str, Any]] = []
        for evidence in evidences:
            text = evidence.get("text") or ""
            if not text.strip():
                continue
            for piece in self._split_evidence_text(text):
                if not piece:
                    continue
                unit = {
                    "text": piece,
                    "doc_id": evidence.get("doc_id"),
                    "page": evidence.get("page"),
                    "chunk_id": evidence.get("chunk_id"),
                }
                units.append(unit)
        return units

    def _split_evidence_text(self, text: str) -> List[str]:
        fragments: List[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            # Split by list markers or long sentences for tighter alignment
            if len(line) > 180:
                clauses = re.split(r"(?<=[.?!])\s+", line)
                fragments.extend([clause.strip() for clause in clauses if clause.strip()])
            else:
                fragments.append(line)
        return fragments or [text.strip()]
