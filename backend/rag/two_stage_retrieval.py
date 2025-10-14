"""
Two-Stage Retrieval for better topic change detection.

Stage 1: Broad search across all documents
Stage 2: Contextual reranking with statistical bonus for context documents
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Result from two-stage retrieval"""
    doc_id: str
    text: str
    original_score: float
    score: float  # Boosted score after context bonus
    is_context_doc: bool
    metadata: Dict[str, Any] = field(default_factory=dict)


class TwoStageRetrieval:
    """
    Two-stage retrieval with automatic topic change detection.

    Strategy:
    1. Search all documents without restriction
    2. Apply statistical bonus to context documents (previous answer's docs)
    3. Detect topic change based on score margin between context and new docs
    """

    def __init__(
        self,
        retriever,
        context_boost: float = 0.15,
        topic_change_threshold: float = 0.10
    ):
        """
        Args:
            retriever: HybridRetriever instance
            context_boost: Score boost for context documents (default 0.15 = 15%)
            topic_change_threshold: Minimum score margin to detect topic change
        """
        self.retriever = retriever
        self.context_boost = context_boost
        self.topic_change_threshold = topic_change_threshold

        logger.info(
            f"[TwoStageRetrieval] Initialized with context_boost={context_boost}, "
            f"threshold={topic_change_threshold}"
        )

    def retrieve(
        self,
        query: str,
        context_doc_ids: List[str],
        topk: int = 10
    ) -> Tuple[List[RetrievalResult], Dict[str, Any]]:
        """
        Perform two-stage retrieval with topic change detection.

        Args:
            query: Search query
            context_doc_ids: Document IDs from previous answer (context)
            topk: Number of results to return

        Returns:
            (results, metadata) where:
                - results: List of RetrievalResult objects
                - metadata: Dict with topic_change_detected, reason, scores, etc.
        """
        logger.info(f"[TwoStageRetrieval] Query: '{query[:50]}...', context_docs: {context_doc_ids}")

        # Stage 1: Broad search across all documents (no restriction)
        try:
            all_results = self.retriever.retrieve(
                query,
                limit=topk * 2,  # Retrieve more to have room for reranking
                document_ids=None  # Search ALL documents
            )
        except Exception as e:
            logger.error(f"[TwoStageRetrieval] Stage 1 retrieval failed: {e}")
            # Fallback: return empty results
            return [], {
                "topic_change_detected": False,
                "reason": "retrieval_failed",
                "error": str(e)
            }

        if not all_results:
            logger.warning("[TwoStageRetrieval] No results from Stage 1")
            return [], {
                "topic_change_detected": False,
                "reason": "no_results"
            }

        # Stage 2: Apply context bonus and separate context vs new docs
        context_set = set(context_doc_ids)
        context_results = []
        new_results = []

        for result in all_results:
            doc_id = result.get("doc_id", "")
            original_score = result.get("normalized_score") or result.get("score", 0.0)

            is_context = doc_id in context_set

            # Apply boost to context documents
            boosted_score = original_score * (1.0 + self.context_boost) if is_context else original_score

            retrieval_result = RetrievalResult(
                doc_id=doc_id,
                text=result.get("text", ""),
                original_score=original_score,
                score=boosted_score,
                is_context_doc=is_context,
                metadata={
                    "page": result.get("page", 0),
                    "chunk_id": result.get("chunk_id", ""),
                    "start_char": result.get("start_char", -1),
                    "end_char": result.get("end_char", -1),
                }
            )

            if is_context:
                context_results.append(retrieval_result)
            else:
                new_results.append(retrieval_result)

        # Sort by boosted score
        context_results.sort(key=lambda x: x.score, reverse=True)
        new_results.sort(key=lambda x: x.score, reverse=True)

        logger.info(
            f"[TwoStageRetrieval] Stage 2 - context docs: {len(context_results)}, "
            f"new docs: {len(new_results)}"
        )

        # Topic change detection based on score margin
        topic_change_detected = False
        topic_reason = "context_preferred"
        best_context_doc = None
        best_context_score = 0.0
        best_new_doc = None
        best_new_score = 0.0
        score_margin = 0.0

        if context_results:
            best_context_doc = context_results[0].doc_id
            best_context_score = context_results[0].score

        if new_results:
            best_new_doc = new_results[0].doc_id
            best_new_score = new_results[0].score

        # Calculate score margin
        if best_context_score > 0 and best_new_score > 0:
            score_margin = best_new_score - best_context_score

            # Topic change if new document significantly beats context document
            if score_margin > self.topic_change_threshold:
                topic_change_detected = True
                topic_reason = f"score_margin_{score_margin:.3f}"
                logger.info(
                    f"[TwoStageRetrieval] Topic change detected: "
                    f"{best_context_doc}({best_context_score:.3f}) → "
                    f"{best_new_doc}({best_new_score:.3f}), margin={score_margin:.3f}"
                )
        elif best_new_score > 0 and not context_results:
            # No context results, definitely topic change
            topic_change_detected = True
            topic_reason = "no_context_results"
            logger.info(f"[TwoStageRetrieval] Topic change: no context results")

        # Merge results: prefer context docs unless topic change
        if topic_change_detected:
            # Topic changed - prioritize new documents
            merged_results = new_results + context_results
        else:
            # Same topic - prioritize context documents
            merged_results = context_results + new_results

        # Limit to topk
        final_results = merged_results[:topk]

        metadata = {
            "topic_change_detected": topic_change_detected,
            "reason": topic_reason,
            "best_context_doc": best_context_doc,
            "best_context_score": best_context_score,
            "best_new_doc": best_new_doc,
            "best_new_score": best_new_score,
            "score_margin": score_margin,
            "context_count": len(context_results),
            "new_count": len(new_results),
            "context_boost": self.context_boost,
            "threshold": self.topic_change_threshold
        }

        logger.info(
            f"[TwoStageRetrieval] Returning {len(final_results)} results, "
            f"topic_change={topic_change_detected}"
        )

        return final_results, metadata


def create_two_stage_retrieval(
    retriever,
    context_boost: float = 0.15,
    topic_change_threshold: float = 0.10
) -> TwoStageRetrieval:
    """
    Factory function to create TwoStageRetrieval instance.

    Args:
        retriever: HybridRetriever instance
        context_boost: Score boost for context documents (default 0.15)
        topic_change_threshold: Minimum margin for topic change (default 0.10)

    Returns:
        TwoStageRetrieval instance
    """
    return TwoStageRetrieval(
        retriever=retriever,
        context_boost=context_boost,
        topic_change_threshold=topic_change_threshold
    )
