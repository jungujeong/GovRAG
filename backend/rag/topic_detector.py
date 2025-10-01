"""
Enhanced topic change detection using retrieval metrics.
No hardcoded keywords; relies on evidence statistics and document overlap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Sequence
import logging

logger = logging.getLogger(__name__)


@dataclass
class TopicChangeAnalysis:
    """Result payload describing whether a topic change is likely."""

    changed: bool
    reason: str
    overlap_ratio: float
    suggested_doc_ids: List[str] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    primary_doc_ids: List[str] = field(default_factory=list)
    expanded_doc_ids: List[str] = field(default_factory=list)
    unbounded_doc_ids: List[str] = field(default_factory=list)


class TopicChangeDetector:
    """Detects topic changes using retrieval scores and document overlap."""

    def __init__(
        self,
        similarity_threshold: float = 0.3,
        retrieval_confidence_threshold: float = 0.2,
        min_score_threshold: float = 0.1,
    ) -> None:
        """Configure detector thresholds.

        Args:
            similarity_threshold: Reserved for embedding-based checks (not yet used)
            retrieval_confidence_threshold: Required improvement to treat other docs as better
            min_score_threshold: Minimum acceptable evidence score for in-scope retrieval
        """
        self.similarity_threshold = similarity_threshold
        self.retrieval_confidence_threshold = retrieval_confidence_threshold
        self.min_score_threshold = min_score_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze(
        self,
        *,
        query: str,
        previous_doc_ids: Sequence[str],
        scoped_evidences: Sequence[Dict[str, Any]],
        expanded_evidences: Optional[Sequence[Dict[str, Any]]] = None,
        unbounded_evidences: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> TopicChangeAnalysis:
        """Analyse whether the query should step outside the previous scope.

        Args:
            query: Current natural language question (unused but logged for traceability)
            previous_doc_ids: Document IDs that define the current scope
            scoped_evidences: Retrieval results restricted to the previous scope
            expanded_evidences: Retrieval results from a wider scope (e.g., session docs)
            unbounded_evidences: Retrieval results without any filter (optional)

        Returns:
            TopicChangeAnalysis describing change decision and supporting metrics
        """
        previous_scope = set(self._sanitize_doc_ids(previous_doc_ids))

        analysis = TopicChangeAnalysis(
            changed=False,
            reason="within_scope",
            overlap_ratio=1.0,
        )

        analysis.primary_doc_ids = self._unique_doc_ids(scoped_evidences)
        analysis.expanded_doc_ids = self._unique_doc_ids(expanded_evidences)
        analysis.unbounded_doc_ids = self._unique_doc_ids(unbounded_evidences)

        metrics = {
            "primary_count": float(len(scoped_evidences or [])),
            "expanded_count": float(len(expanded_evidences or [])),
            "unbounded_count": float(len(unbounded_evidences or [])),
        }

        metrics.update(self._score_metrics(scoped_evidences, prefix="primary"))
        metrics.update(self._score_metrics(expanded_evidences, prefix="expanded"))
        metrics.update(self._score_metrics(unbounded_evidences, prefix="unbounded"))

        analysis.metrics = metrics

        if not previous_scope:
            analysis.reason = "no_previous_scope"
            return analysis

        # Condition 1: no evidence in current scope
        if not scoped_evidences:
            logger.info("Topic change: no evidences in previous scope")
            analysis.changed = True
            analysis.reason = "no_primary_evidence"
            analysis.overlap_ratio = 0.0
            analysis.suggested_doc_ids = analysis.expanded_doc_ids or analysis.unbounded_doc_ids
            return analysis

        # Condition 2: low confidence within scope
        if metrics["primary_avg_score"] < self.min_score_threshold:
            logger.info(
                "Topic change: primary average score %.3f below threshold %.3f",
                metrics["primary_avg_score"],
                self.min_score_threshold,
            )
            analysis.changed = True
            analysis.reason = "low_primary_score"
        elif metrics["primary_max_score"] < self.min_score_threshold * 1.5 and metrics["primary_count"] <= 2:
            logger.info(
                "Topic change: max primary score %.3f insufficient",
                metrics["primary_max_score"],
            )
            analysis.changed = True
            analysis.reason = "weak_primary_hits"

        # Condition 3: wider scope contains significantly better docs
        candidate_docs: List[str] = []
        overlap_ratio = 1.0
        if expanded_evidences:
            overlap_ratio = self._overlap_ratio(previous_scope, analysis.expanded_doc_ids)
            new_docs = [doc_id for doc_id in analysis.expanded_doc_ids if doc_id not in previous_scope]
            metrics["expanded_new_doc_ratio"] = (
                float(len(new_docs)) / float(len(analysis.expanded_doc_ids))
                if analysis.expanded_doc_ids
                else 0.0
            )
            metrics["expanded_avg_delta"] = (
                metrics["expanded_avg_score"] - metrics["primary_avg_score"]
            )
            metrics["expanded_max_delta"] = (
                metrics["expanded_max_score"] - metrics["primary_max_score"]
            )

            if new_docs:
                candidate_docs.extend(new_docs)
                better_avg = metrics["expanded_avg_delta"] >= self.retrieval_confidence_threshold
                better_max = metrics["expanded_max_delta"] >= self.retrieval_confidence_threshold * 1.5
                poor_overlap = overlap_ratio < 0.4

                if better_avg or better_max or poor_overlap:
                    logger.info(
                        "Topic change: better matches in expanded scope (avg_delta=%.3f, max_delta=%.3f, overlap=%.2f)",
                        metrics["expanded_avg_delta"],
                        metrics["expanded_max_delta"],
                        overlap_ratio,
                    )
                    analysis.changed = True
                    analysis.reason = "better_results_elsewhere"

        if not analysis.changed and not candidate_docs and unbounded_evidences:
            new_docs_unbounded = [
                doc_id for doc_id in analysis.unbounded_doc_ids if doc_id not in previous_scope
            ]
            if new_docs_unbounded:
                candidate_docs.extend(new_docs_unbounded)
                logger.info(
                    "Topic change candidate: unbounded search exposes new docs %s",
                    new_docs_unbounded,
                )
                analysis.changed = True
                analysis.reason = "unbounded_has_new_docs"

        analysis.overlap_ratio = overlap_ratio

        if analysis.changed and not candidate_docs:
            candidate_docs = analysis.expanded_doc_ids or analysis.unbounded_doc_ids

        analysis.suggested_doc_ids = candidate_docs

        if analysis.changed:
            logger.info(
                "Topic change detected (reason=%s, suggested=%s)",
                analysis.reason,
                candidate_docs,
            )

        return analysis

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _unique_doc_ids(self, evidences: Optional[Sequence[Dict[str, Any]]]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        if not evidences:
            return ordered
        for evidence in evidences:
            doc_id = evidence.get("doc_id")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            ordered.append(doc_id)
        return ordered

    def _score_metrics(self, evidences: Optional[Sequence[Dict[str, Any]]], prefix: str) -> Dict[str, float]:
        if not evidences:
            return {
                f"{prefix}_avg_score": 0.0,
                f"{prefix}_max_score": 0.0,
            }
        scores = [self._normalize_score(ev) for ev in evidences if self._normalize_score(ev) is not None]
        if not scores:
            return {
                f"{prefix}_avg_score": 0.0,
                f"{prefix}_max_score": 0.0,
            }
        return {
            f"{prefix}_avg_score": sum(scores) / len(scores),
            f"{prefix}_max_score": max(scores),
        }

    def _normalize_score(self, evidence: Dict[str, Any]) -> Optional[float]:
        score = evidence.get("normalized_score")
        if score is None:
            score = evidence.get("score", evidence.get("similarity", evidence.get("relevance")))
        if score is None:
            return None
        try:
            score_f = float(score)
        except (TypeError, ValueError):
            return None
        if score_f > 1.0:
            score_f = score_f / 100.0
        return max(0.0, min(score_f, 1.0))

    def _overlap_ratio(self, previous_scope: set, expanded_doc_ids: Sequence[str]) -> float:
        if not expanded_doc_ids:
            return 1.0
        expanded_set = set(expanded_doc_ids)
        if not expanded_set:
            return 1.0
        return len(previous_scope.intersection(expanded_set)) / len(expanded_set)

    def _sanitize_doc_ids(self, doc_ids: Sequence[str]) -> List[str]:
        if not doc_ids:
            return []
        sanitized = []
        seen = set()
        for doc_id in doc_ids:
            if not doc_id or doc_id in seen:
                continue
            sanitized.append(doc_id)
            seen.add(doc_id)
        return sanitized
