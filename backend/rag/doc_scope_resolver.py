"""Utility to resolve evidence scope per query without hardcoded rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence
import logging
import sys

from rag.topic_detector import TopicChangeDetector, TopicChangeAnalysis
from rag.two_stage_retrieval import TwoStageRetrieval, create_two_stage_retrieval

logger = logging.getLogger(__name__)

def debug_print(msg: str):
    """Print debug message to stderr"""
    print(f"[DEBUG-SCOPE] {msg}", file=sys.stderr, flush=True)


@dataclass
class DocScopeResolution:
    """Result returned by :class:`DocScopeResolver`."""

    evidences: List[Dict[str, Any]]
    allowed_doc_ids: Optional[List[str]]
    doc_scope_mode: str
    doc_scope_ids: List[str]
    resolved_doc_ids: List[str]
    average_score: Optional[float]
    topic_change_detected: bool
    topic_change_reason: Optional[str]
    topic_change_suggested: List[str] = field(default_factory=list)
    allow_fixed_citations: bool = False
    status: str = "ok"
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    diagnostics: Dict[str, Any] = field(default_factory=dict)


class DocScopeResolver:
    """
    Resolves which documents should be searched for a given query.

    Now uses TwoStageRetrieval for better topic change detection and context handling.
    """

    def __init__(
        self,
        topic_detector: TopicChangeDetector,
        use_two_stage: bool = True
    ) -> None:
        self.topic_detector = topic_detector
        self.use_two_stage = use_two_stage
        self.two_stage_retrieval: Optional[TwoStageRetrieval] = None

        logger.info(f"[DocScopeResolver] Initialized with use_two_stage={use_two_stage}")

    def resolve(
        self,
        *,
        query: str,
        retrieval_query: str,
        retriever,
        requested_doc_ids: Optional[Sequence[str]],
        session_doc_ids: Optional[Sequence[str]],
        previous_doc_ids: Optional[Sequence[str]],
        should_use_previous_sources: bool,
        topk: int,
        allow_topic_expansion: bool = True,
    ) -> DocScopeResolution:
        """
        Resolve evidences and document scope for a single turn.

        Now uses TwoStageRetrieval when enabled:
        - Stage 1: Broad search across all documents
        - Stage 2: Contextual reranking with statistical bonus
        - Automatic topic change detection based on score margins
        """
        debug_print(f"Input - requested: {requested_doc_ids}, session: {session_doc_ids}, previous: {previous_doc_ids}")
        requested_scope = self._deduplicate(requested_doc_ids)
        session_scope = self._deduplicate(session_doc_ids)
        previous_scope = self._deduplicate(previous_doc_ids)
        debug_print(f"Normalized - requested: {requested_scope}, session: {session_scope}, previous: {previous_scope}")

        metadata: Dict[str, Any] = {
            "requested_doc_ids": requested_scope,
            "session_doc_ids": session_scope,
            "previous_doc_ids": previous_scope,
        }

        doc_scope_mode = "session"
        scope_ids = session_scope
        allow_fixed_citations = False

        if requested_scope:
            doc_scope_mode = "requested"
            scope_ids = requested_scope
        elif should_use_previous_sources and previous_scope:
            doc_scope_mode = "followup"
            scope_ids = previous_scope
            # 첫 답변 evidences 재사용 로직 제거 - 항상 새로 검색
            allow_fixed_citations = False
        elif not session_scope:
            doc_scope_mode = "unbounded"
            scope_ids = []

        # ===== TWO-STAGE RETRIEVAL (NEW) =====
        # Only use TwoStageRetrieval in followup mode when we have previous sources
        # Session mode searches all session docs, so Two-Stage isn't needed
        if self.use_two_stage and doc_scope_mode == "followup" and previous_scope:
            # Initialize TwoStageRetrieval on first use
            if self.two_stage_retrieval is None:
                self.two_stage_retrieval = create_two_stage_retrieval(retriever)

            # Use TwoStageRetrieval for automatic topic handling
            # Context = previous answer's documents
            context_doc_ids = previous_scope
            results, two_stage_metadata = self.two_stage_retrieval.retrieve(
                query=retrieval_query,
                context_doc_ids=context_doc_ids,
                topk=topk
            )

            # Convert RetrievalResult objects to evidence dicts
            # Flatten metadata to top-level for compatibility with citation_tracker
            evidences = [
                {
                    "doc_id": res.doc_id,
                    "text": res.text,
                    "score": res.original_score,
                    "normalized_score": res.original_score,
                    # Flatten metadata fields to top-level
                    "page": res.metadata.get("page", 0),
                    "chunk_id": res.metadata.get("chunk_id", ""),
                    "start_char": res.metadata.get("start_char", -1),
                    "end_char": res.metadata.get("end_char", -1),
                    "metadata": res.metadata,  # Keep original for backward compatibility
                    "_is_context_doc": res.is_context_doc,
                    "_boosted_score": res.score
                }
                for res in results
            ]

            # Extract topic change detection from TwoStageRetrieval
            topic_change_detected = two_stage_metadata.get("topic_change_detected", False)
            topic_reason = two_stage_metadata.get("reason", "two_stage_detection")

            if topic_change_detected:
                # Update scope to include new documents
                new_doc_id = two_stage_metadata.get("best_new_doc")
                if new_doc_id:
                    scope_ids = [new_doc_id]
                    doc_scope_mode = "expanded"
                    allow_fixed_citations = False

                logger.info(
                    f"[DocScopeResolver] TwoStage detected topic change: "
                    f"{two_stage_metadata.get('best_context_doc')}({two_stage_metadata.get('best_context_score', 0):.3f}) "
                    f"→ {new_doc_id}({two_stage_metadata.get('best_new_score', 0):.3f}), "
                    f"margin={two_stage_metadata.get('score_margin', 0):.3f}"
                )

            metadata["two_stage"] = two_stage_metadata
            diagnostics = {
                "primary_count": len(evidences),
                "two_stage_used": True,
                "topic_detection_method": "two_stage"
            }

            debug_print(f"TwoStage - mode={doc_scope_mode}, evidences_count={len(evidences)}, topic_change={topic_change_detected}")

        else:
            # ===== LEGACY SINGLE-STAGE RETRIEVAL =====
            evidences = self._safe_retrieve(
                retriever,
                retrieval_query,
                topk,
                scope_ids if scope_ids else None,
            )

            debug_print(f"After retrieve - mode={doc_scope_mode}, scope_ids={scope_ids}, evidences_count={len(evidences)}")
            diagnostics = {
                "primary_count": len(evidences),
                "two_stage_used": False
            }
            topic_change_detected = False
            topic_reason = None

        # Requested scope with no evidences — return early so the caller can notify the user
        if doc_scope_mode == "requested" and not evidences:
            message = "지정된 문서 범위에서 관련 정보를 찾을 수 없습니다. 다른 문서를 선택하거나 질문을 수정해 주세요."
            logger.info("Doc scope resolver: requested scope returned no evidences")
            return DocScopeResolution(
                evidences=[],
                allowed_doc_ids=scope_ids,
                doc_scope_mode=doc_scope_mode,
                doc_scope_ids=scope_ids,
                resolved_doc_ids=[],
                average_score=None,
                topic_change_detected=False,
                topic_change_reason=None,
                allow_fixed_citations=False,
                status="no_evidence",
                error_message=message,
                metadata={**metadata, "mode": doc_scope_mode, "doc_scope_ids": scope_ids},
                diagnostics=diagnostics,
            )

        # Initialize these variables for legacy path
        if not self.use_two_stage:
            topic_change_detected = False
            topic_reason: Optional[str] = None
        topic_suggested: List[str] = []

        # ===== LEGACY TOPIC DETECTION (only if TwoStage not used) =====
        if (
            not self.use_two_stage
            and allow_topic_expansion
            and doc_scope_mode == "followup"
            and previous_scope
        ):
            expanded_evidences = self._safe_retrieve(
                retriever,
                retrieval_query,
                topk,
                session_scope if session_scope else None,
            )
            unbounded_evidences = []
            if session_scope:
                # Avoid redundant retrieval when session scope already equals previous scope
                if set(session_scope) != set(previous_scope):
                    diagnostics["expanded_count"] = len(expanded_evidences)
                else:
                    diagnostics["expanded_count"] = len(expanded_evidences)
            else:
                diagnostics["expanded_count"] = len(expanded_evidences)
            # Always allow an unbounded peek to detect completely new docs
            unbounded_evidences = self._safe_retrieve(
                retriever,
                retrieval_query,
                topk,
                None,
            )
            diagnostics["unbounded_count"] = len(unbounded_evidences)

            analysis: TopicChangeAnalysis = self.topic_detector.analyze(
                query=query,
                previous_doc_ids=previous_scope,
                scoped_evidences=evidences,
                expanded_evidences=expanded_evidences,
                unbounded_evidences=unbounded_evidences,
            )

            metadata["topic_detection"] = {
                "reason": analysis.reason,
                "overlap_ratio": analysis.overlap_ratio,
                "metrics": analysis.metrics,
                "primary_doc_ids": analysis.primary_doc_ids,
                "expanded_doc_ids": analysis.expanded_doc_ids,
                "unbounded_doc_ids": analysis.unbounded_doc_ids,
            }

            diagnostics["topic_reason"] = analysis.reason
            diagnostics["topic_metrics"] = analysis.metrics

            if analysis.changed:
                topic_change_detected = True
                topic_reason = analysis.reason
                topic_suggested = self._deduplicate(analysis.suggested_doc_ids)

                # Determine the new scope. Prefer suggested doc IDs.
                new_scope = topic_suggested or analysis.expanded_doc_ids or analysis.unbounded_doc_ids
                new_scope = self._deduplicate(new_scope)

                logger.info(
                    "Doc scope resolver: expanding scope due to topic change (%s) -> %s",
                    topic_reason,
                    new_scope,
                )

                if new_scope:
                    scope_ids = new_scope
                    doc_scope_mode = "expanded"
                else:
                    doc_scope_mode = "expanded"

                allow_fixed_citations = False
                evidences = self._filter_to_scope(
                    expanded_evidences or unbounded_evidences or evidences,
                    scope_ids,
                    topk,
                )

                if not evidences:
                    # Last resort, try unbounded again to populate evidences
                    evidences = self._safe_retrieve(
                        retriever,
                        retrieval_query,
                        topk,
                        scope_ids if scope_ids else None,
                    )

        if not evidences:
            message = "업로드된 문서에서 해당 정보를 찾을 수 없습니다."
            logger.error(f"[DEBUG] DocScopeResolver FINAL CHECK: no evidences! mode={doc_scope_mode}, scope_ids={scope_ids}, diagnostics={diagnostics}")
            logger.info("Doc scope resolver: no evidences after resolution")
            return DocScopeResolution(
                evidences=[],
                allowed_doc_ids=scope_ids if scope_ids else None,
                doc_scope_mode=doc_scope_mode,
                doc_scope_ids=scope_ids,
                resolved_doc_ids=[],
                average_score=None,
                topic_change_detected=topic_change_detected,
                topic_change_reason=topic_reason,
                topic_change_suggested=topic_suggested,
                allow_fixed_citations=False,
                status="no_evidence",
                error_message=message,
                metadata={**metadata, "mode": doc_scope_mode, "doc_scope_ids": scope_ids},
                diagnostics=diagnostics,
            )

        resolved_doc_ids = self._extract_doc_ids(evidences)
        average_score = self._average_score(evidences)

        metadata.update(
            {
                "mode": doc_scope_mode,
                "doc_scope": doc_scope_mode,
                "doc_scope_ids": scope_ids,
                "resolved_doc_ids": resolved_doc_ids,
                "average_score": average_score,
                "topic_change_detected": topic_change_detected,
                "topic_change_reason": topic_reason,
                "suggested_doc_ids": topic_suggested,
            }
        )

        allowed_doc_ids = scope_ids if scope_ids else None

        return DocScopeResolution(
            evidences=evidences,
            allowed_doc_ids=allowed_doc_ids,
            doc_scope_mode=doc_scope_mode,
            doc_scope_ids=scope_ids,
            resolved_doc_ids=resolved_doc_ids,
            average_score=average_score,
            topic_change_detected=topic_change_detected,
            topic_change_reason=topic_reason,
            topic_change_suggested=topic_suggested,
            allow_fixed_citations=allow_fixed_citations,
            metadata=metadata,
            diagnostics=diagnostics,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _normalize_doc_id(self, doc_id: str) -> str:
        """Normalize document ID by removing file extensions"""
        if not doc_id:
            return doc_id
        # Remove common file extensions
        for ext in ['.pdf', '.PDF', '.hwp', '.HWP', '.txt', '.TXT']:
            if doc_id.endswith(ext):
                return doc_id[:-len(ext)]
        return doc_id

    def _deduplicate(self, doc_ids: Optional[Sequence[str]]) -> List[str]:
        if not doc_ids:
            return []
        seen = set()
        ordered: List[str] = []
        for doc_id in doc_ids:
            if not doc_id:
                continue
            # Normalize doc_id by removing file extension
            normalized = self._normalize_doc_id(doc_id)
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    def _safe_retrieve(
        self,
        retriever,
        query: str,
        topk: int,
        document_ids: Optional[Sequence[str]],
    ) -> List[Dict[str, Any]]:
        try:
            debug_print(f"_safe_retrieve - query='{query[:30]}...', topk={topk}, doc_ids={document_ids}")
            results = retriever.retrieve(
                query,
                limit=topk,
                document_ids=list(document_ids) if document_ids else None,
            )
            debug_print(f"_safe_retrieve returned {len(results)} evidences")
            return results
        except Exception as exc:
            debug_print(f"Retrieval failed: {exc}")
            logger.error("Hybrid retrieval failed: %s", exc)
            return []

    def _average_score(self, evidences: Iterable[Dict[str, Any]]) -> Optional[float]:
        scores: List[float] = []
        for evidence in evidences:
            score = evidence.get("normalized_score")
            if score is None:
                score = evidence.get("score", evidence.get("similarity", evidence.get("relevance")))
            if score is None:
                continue
            try:
                score_f = float(score)
            except (TypeError, ValueError):
                continue
            if score_f > 1.0:
                score_f = score_f / 100.0
            scores.append(score_f)
        if not scores:
            return None
        return sum(scores) / len(scores)

    def _extract_doc_ids(self, evidences: Iterable[Dict[str, Any]]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for evidence in evidences:
            doc_id = evidence.get("doc_id")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            ordered.append(doc_id)
        return ordered

    def _filter_to_scope(
        self,
        evidences: Sequence[Dict[str, Any]],
        scope_ids: Sequence[str],
        topk: int,
    ) -> List[Dict[str, Any]]:
        if not scope_ids:
            return list(evidences)[:topk]
        scope_set = set(scope_ids)
        filtered: List[Dict[str, Any]] = []
        for evidence in evidences:
            if evidence.get("doc_id") in scope_set:
                filtered.append(evidence)
                if len(filtered) >= topk:
                    break
        return filtered
