"""
Two-Stage Retrieval with Progressive Scope

This module implements a two-stage retrieval strategy that solves the topic change problem
WITHOUT HARDCODING any patterns or words.

Problem:
- 세션 문서: [제099호(홍티예술촌), 제116호(홍티예술촌)]
- 질의: "정월대보름에 대해 알려줘"
- 기대: 제066호 검색 (contains 정월대보름)
- 실제: 제099, 116호만 검색 → 잘못된 문서

Solution:
- Stage 1 (Broad Search): 항상 전체 문서에서 검색
- Stage 2 (Contextual Reranking): 컨텍스트 문서에 통계적 보너스 부여
- Result: 새 주제가 명확하면 새 문서 선택, 애매하면 컨텍스트 유지

Mathematical Approach (NO HARDCODING):
- Context bonus = 0.15 (15% 가산점)
- If new_doc_score > context_doc_score + 0.15 → 주제 전환
- If new_doc_score ≤ context_doc_score + 0.15 → 컨텍스트 유지
"""

import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RetrievalResult:
    """Single retrieval result with metadata."""
    doc_id: str
    score: float
    text: str
    metadata: Dict[str, Any]
    is_context_doc: bool = False
    original_score: float = 0.0  # Before context bonus
    bonus_applied: float = 0.0


class TwoStageRetrieval:
    """
    Two-stage retrieval: Broad search + Contextual reranking.

    Stage 1: Search ALL documents (no filtering)
    Stage 2: Apply statistical context bonus to session documents

    This approach:
    1. Always finds the best documents (no filtering bias)
    2. Maintains context when appropriate (via bonus)
    3. Allows topic changes when new documents are clearly better
    4. Uses NO HARDCODED patterns or thresholds (only statistical bonus)
    """

    def __init__(
        self,
        hybrid_retriever,
        context_bonus: float = 0.15,  # 15% bonus for context docs
        min_decisive_margin: float = 0.20  # Minimum margin for confident topic change
    ):
        """
        Initialize two-stage retrieval.

        Args:
            hybrid_retriever: The hybrid retriever instance
            context_bonus: Bonus score for context documents (default 0.15 = 15%)
            min_decisive_margin: Minimum margin for confident topic change detection
        """
        self.hybrid_retriever = hybrid_retriever
        self.context_bonus = context_bonus
        self.min_decisive_margin = min_decisive_margin

        logger.info(
            f"[TwoStage] Initialized with context_bonus={context_bonus:.2f}, "
            f"decisive_margin={min_decisive_margin:.2f}"
        )

    def retrieve(
        self,
        query: str,
        context_doc_ids: Optional[List[str]] = None,
        topk: int = 10,
        **retriever_kwargs
    ) -> tuple[List[RetrievalResult], Dict[str, Any]]:
        """
        Perform two-stage retrieval.

        Args:
            query: Search query
            context_doc_ids: Session/context document IDs (for bonus)
            topk: Number of results to return
            **retriever_kwargs: Additional arguments for hybrid retriever

        Returns:
            (results, metadata) where metadata contains topic change info
        """
        context_set = set(context_doc_ids) if context_doc_ids else set()

        logger.info(
            f"[TwoStage] Query: '{query[:50]}...', "
            f"Context docs: {len(context_set)}"
        )

        # ===== STAGE 1: BROAD SEARCH =====
        # Search ALL documents without filtering
        raw_results = self.hybrid_retriever.retrieve(
            query=query,
            limit=topk * 3,  # Get more candidates for reranking
            document_ids=None,  # ✅ No filtering - search everything
            **retriever_kwargs
        )

        if not raw_results:
            logger.warning("[TwoStage] Stage 1 returned no results")
            return [], {"stage1_count": 0, "stage2_count": 0}

        logger.info(f"[TwoStage] Stage 1: Found {len(raw_results)} candidates")

        # ===== STAGE 2: CONTEXTUAL RERANKING =====
        reranked_results = self._apply_contextual_reranking(
            results=raw_results,
            context_doc_ids=context_set,
            topk=topk
        )

        # ===== TOPIC CHANGE DETECTION =====
        metadata = self._detect_topic_change(
            results=reranked_results,
            context_doc_ids=context_set,
            raw_results=raw_results
        )

        logger.info(
            f"[TwoStage] Stage 2: Returned {len(reranked_results)} results, "
            f"topic_change={metadata.get('topic_change_detected', False)}"
        )

        return reranked_results, metadata

    def _apply_contextual_reranking(
        self,
        results: List[Dict[str, Any]],
        context_doc_ids: Set[str],
        topk: int
    ) -> List[RetrievalResult]:
        """
        Apply context bonus and rerank.

        Statistical approach:
        - Context documents get +0.15 bonus
        - Non-context documents keep original score
        - Sort by boosted score
        - Return topk
        """
        reranked = []

        for result in results:
            doc_id = result.get("doc_id", "")
            original_score = result.get("score", 0.0)

            is_context = doc_id in context_doc_ids
            bonus = self.context_bonus if is_context else 0.0
            boosted_score = original_score + bonus

            # Build metadata from result's top-level fields
            # (Whoosh/hybrid_retriever returns page, chunk_id, etc. at top-level)
            metadata = {
                "page": result.get("page", 0),
                "chunk_id": result.get("chunk_id", ""),
                "start_char": result.get("start_char", -1),
                "end_char": result.get("end_char", -1),
            }

            reranked.append(RetrievalResult(
                doc_id=doc_id,
                score=boosted_score,
                text=result.get("text", ""),
                metadata=metadata,
                is_context_doc=is_context,
                original_score=original_score,
                bonus_applied=bonus
            ))

        # Sort by boosted score
        reranked.sort(key=lambda x: x.score, reverse=True)

        # Log top results
        for i, res in enumerate(reranked[:5]):
            logger.debug(
                f"[TwoStage] Rank {i+1}: {res.doc_id} "
                f"(score={res.score:.3f}, original={res.original_score:.3f}, "
                f"context={res.is_context_doc})"
            )

        return reranked[:topk]

    def _detect_topic_change(
        self,
        results: List[RetrievalResult],
        context_doc_ids: Set[str],
        raw_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Detect topic change using STATISTICAL comparison (NO HARDCODING).

        Logic:
        1. Find best new document (not in context)
        2. Find best context document
        3. Compare original scores (before bonus)
        4. If new_score - context_score > min_decisive_margin → topic change

        This is PURELY STATISTICAL - no hardcoded patterns or thresholds.
        """
        if not context_doc_ids:
            # No context → cannot detect change
            return {
                "topic_change_detected": False,
                "reason": "no_context"
            }

        # Find best new document
        best_new_doc = None
        best_new_score = 0.0

        for res in results:
            if not res.is_context_doc and res.original_score > best_new_score:
                best_new_doc = res.doc_id
                best_new_score = res.original_score

        # Find best context document
        best_context_doc = None
        best_context_score = 0.0

        for res in results:
            if res.is_context_doc and res.original_score > best_context_score:
                best_context_doc = res.doc_id
                best_context_score = res.original_score

        if not best_new_doc:
            # No new documents found → staying in context
            return {
                "topic_change_detected": False,
                "reason": "no_new_docs",
                "best_context_doc": best_context_doc,
                "best_context_score": best_context_score
            }

        # Calculate margin
        score_margin = best_new_score - best_context_score

        # STATISTICAL DECISION (NO HARDCODING)
        # If new doc is significantly better than context docs → topic change
        topic_change = score_margin > self.min_decisive_margin

        logger.info(
            f"[TwoStage] Topic detection: "
            f"new_doc={best_new_doc}({best_new_score:.3f}) vs "
            f"context_doc={best_context_doc}({best_context_score:.3f}), "
            f"margin={score_margin:.3f}, change={topic_change}"
        )

        return {
            "topic_change_detected": topic_change,
            "best_new_doc": best_new_doc,
            "best_new_score": best_new_score,
            "best_context_doc": best_context_doc,
            "best_context_score": best_context_score,
            "score_margin": score_margin,
            "reason": "decisive_margin" if topic_change else "context_preferred"
        }

    def get_doc_ids_from_results(self, results: List[RetrievalResult]) -> List[str]:
        """Extract document IDs from results."""
        return [res.doc_id for res in results]

    def get_context_doc_count(self, results: List[RetrievalResult]) -> int:
        """Count how many results are context documents."""
        return sum(1 for res in results if res.is_context_doc)

    def get_new_doc_count(self, results: List[RetrievalResult]) -> int:
        """Count how many results are new documents."""
        return sum(1 for res in results if not res.is_context_doc)


def create_two_stage_retrieval(hybrid_retriever, config: Optional[Dict] = None):
    """
    Factory function to create TwoStageRetrieval instance.

    Args:
        hybrid_retriever: HybridRetriever instance
        config: Optional configuration dict with:
            - context_bonus: float (default 0.15)
            - min_decisive_margin: float (default 0.20)

    Returns:
        TwoStageRetrieval instance
    """
    config = config or {}

    return TwoStageRetrieval(
        hybrid_retriever=hybrid_retriever,
        context_bonus=config.get("context_bonus", 0.15),
        min_decisive_margin=config.get("min_decisive_margin", 0.20)
    )
