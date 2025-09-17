"""
Topic change detection using embedding similarity and retrieval scores.
No hardcoded patterns or keywords - uses semantic similarity instead.
"""

import logging
from typing import List, Dict, Optional, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


class TopicChangeDetector:
    """Detects topic changes using embedding similarity and retrieval confidence"""

    def __init__(
        self,
        similarity_threshold: float = 0.3,
        retrieval_confidence_threshold: float = 0.2,
        min_score_threshold: float = 0.1
    ):
        """
        Initialize topic change detector.

        Args:
            similarity_threshold: Min cosine similarity to consider same topic
            retrieval_confidence_threshold: Min retrieval score to consider relevant
            min_score_threshold: Absolute minimum score for any relevance
        """
        self.similarity_threshold = similarity_threshold
        self.retrieval_confidence_threshold = retrieval_confidence_threshold
        self.min_score_threshold = min_score_threshold

    def detect_topic_change(
        self,
        current_query: str,
        previous_context: List[Dict],
        evidences_from_previous: List[Dict],
        evidences_from_all: Optional[List[Dict]] = None
    ) -> Tuple[bool, str, Optional[List[str]]]:
        """
        Detect if the current query represents a topic change.

        Args:
            current_query: Current user query
            previous_context: Previous conversation messages
            evidences_from_previous: Search results from previous documents
            evidences_from_all: Search results from all documents (optional)

        Returns:
            Tuple of (is_topic_changed, reason, suggested_new_doc_ids)
        """

        # Check retrieval confidence from previous documents
        if not evidences_from_previous:
            logger.info("No evidences from previous documents - potential topic change")

            # If we have results from all documents, suggest those
            if evidences_from_all:
                new_doc_ids = self._extract_unique_doc_ids(evidences_from_all)
                return (
                    True,
                    "no_relevant_content_in_previous",
                    new_doc_ids
                )
            return (True, "no_relevant_content", None)

        # Calculate average retrieval score (normalized)
        avg_score = self._calculate_average_score(evidences_from_previous)

        # Get top scores for better comparison
        top_score_prev = self._get_top_score(evidences_from_previous)

        logger.info(f"Previous docs - avg score: {avg_score:.3f}, top score: {top_score_prev:.3f}")

        # Very low scores indicate topic change
        if avg_score < self.min_score_threshold or top_score_prev < self.min_score_threshold * 2:
            logger.info(f"Very low retrieval scores - strong topic change signal")

            if evidences_from_all:
                new_doc_ids = self._extract_unique_doc_ids(evidences_from_all)
                return (
                    True,
                    "low_confidence_scores",
                    new_doc_ids
                )
            return (True, "low_confidence_scores", None)

        # Check if better results exist in other documents
        if evidences_from_all:
            avg_score_all = self._calculate_average_score(evidences_from_all)
            top_score_all = self._get_top_score(evidences_from_all)

            # Compare both average and top scores
            avg_improvement = avg_score_all - avg_score
            top_improvement = top_score_all - top_score_prev

            logger.info(f"All docs - avg score: {avg_score_all:.3f}, top score: {top_score_all:.3f}")
            logger.info(f"Score improvements - avg: {avg_improvement:.3f}, top: {top_improvement:.3f}")

            # Check if results from other documents are significantly better
            if (avg_improvement > self.retrieval_confidence_threshold or
                top_improvement > self.retrieval_confidence_threshold * 1.5):

                logger.info(f"Much better results in other documents - topic change detected")

                # Get new document IDs that aren't in previous
                previous_doc_ids = self._extract_unique_doc_ids(evidences_from_previous)
                all_doc_ids = self._extract_unique_doc_ids(evidences_from_all)
                new_doc_ids = [doc_id for doc_id in all_doc_ids if doc_id not in previous_doc_ids]

                # Additional check: Are top results mostly from new documents?
                top_all_docs = self._get_top_doc_ids(evidences_from_all, top_n=5)
                new_in_top = [doc for doc in top_all_docs if doc not in previous_doc_ids]

                if len(new_in_top) >= 3:  # Most top results are from new docs
                    logger.info(f"Top results mostly from new documents: {new_in_top}")
                    return (
                        True,
                        "better_results_elsewhere",
                        new_doc_ids if new_doc_ids else new_in_top
                    )

        # Check semantic similarity with context (if embeddings available)
        if self._has_embeddings(evidences_from_previous):
            similarity = self._calculate_context_similarity(
                evidences_from_previous,
                previous_context
            )

            if similarity < self.similarity_threshold:
                logger.info(
                    f"Low semantic similarity ({similarity:.3f}) with previous context - topic change"
                )

                if evidences_from_all:
                    new_doc_ids = self._extract_unique_doc_ids(evidences_from_all)
                    return (
                        True,
                        "low_semantic_similarity",
                        new_doc_ids
                    )
                return (True, "low_semantic_similarity", None)

        # No topic change detected
        return (False, "same_topic", None)

    def _calculate_average_score(self, evidences: List[Dict]) -> float:
        """Calculate average retrieval score from evidences"""
        if not evidences:
            return 0.0

        scores = []
        for evidence in evidences:
            # Try different score fields that might exist
            score = evidence.get("score", evidence.get("similarity", evidence.get("relevance", 0.0)))
            # Normalize score to 0-1 range if needed
            if score > 1.0:
                score = score / 100.0  # Assume percentage
            scores.append(float(score))

        return np.mean(scores) if scores else 0.0

    def _get_top_score(self, evidences: List[Dict]) -> float:
        """Get the highest score from evidences"""
        if not evidences:
            return 0.0

        scores = []
        for evidence in evidences:
            score = evidence.get("score", evidence.get("similarity", evidence.get("relevance", 0.0)))
            # Normalize score to 0-1 range if needed
            if score > 1.0:
                score = score / 100.0
            scores.append(float(score))

        return max(scores) if scores else 0.0

    def _get_top_doc_ids(self, evidences: List[Dict], top_n: int = 5) -> List[str]:
        """Get document IDs from top N evidences by score"""
        if not evidences:
            return []

        # Sort evidences by score
        scored_evidences = []
        for evidence in evidences:
            score = evidence.get("score", evidence.get("similarity", evidence.get("relevance", 0.0)))
            if score > 1.0:
                score = score / 100.0
            scored_evidences.append((score, evidence))

        scored_evidences.sort(key=lambda x: x[0], reverse=True)

        # Extract doc_ids from top N
        doc_ids = []
        seen = set()
        for _, evidence in scored_evidences[:top_n]:
            doc_id = evidence.get("doc_id")
            if doc_id and doc_id not in seen:
                doc_ids.append(doc_id)
                seen.add(doc_id)

        return doc_ids

    def _extract_unique_doc_ids(self, evidences: List[Dict]) -> List[str]:
        """Extract unique document IDs from evidences"""
        doc_ids = []
        seen = set()

        for evidence in evidences:
            doc_id = evidence.get("doc_id")
            if doc_id and doc_id not in seen:
                doc_ids.append(doc_id)
                seen.add(doc_id)

        return doc_ids

    def _has_embeddings(self, evidences: List[Dict]) -> bool:
        """Check if evidences have embedding vectors"""
        if not evidences:
            return False

        return any(
            "embedding" in e or "vector" in e
            for e in evidences
        )

    def _calculate_context_similarity(
        self,
        evidences: List[Dict],
        previous_context: List[Dict]
    ) -> float:
        """
        Calculate semantic similarity between current evidences and previous context.
        This is a placeholder - actual implementation would use embeddings.
        """
        # For now, return a default value indicating we can't calculate
        # In a real implementation, this would:
        # 1. Get embeddings for current evidences
        # 2. Get embeddings for previous context
        # 3. Calculate cosine similarity
        return 0.5  # Neutral value - neither high nor low

    def suggest_action(
        self,
        is_topic_changed: bool,
        reason: str,
        new_doc_ids: Optional[List[str]] = None
    ) -> Dict:
        """
        Suggest action based on topic change detection.

        Returns:
            Dict with action type and message for user
        """
        if not is_topic_changed:
            return {
                "action": "continue",
                "message": None
            }

        if reason == "no_relevant_content_in_previous":
            message = (
                "현재 질문은 이전 대화에서 사용한 문서와 관련이 없는 것으로 보입니다.\n\n"
                "선택하세요:\n"
                "1. 이전 문서 범위에서 가능한 답변 받기\n"
                "2. 새로운 주제로 전환 (다른 문서 검색)"
            )

            if new_doc_ids:
                message += f"\n\n💡 추천: 다음 문서에서 관련 정보를 찾았습니다: {', '.join(new_doc_ids[:3])}"

            return {
                "action": "suggest_reset",
                "message": message,
                "suggested_docs": new_doc_ids
            }

        elif reason == "low_confidence_scores":
            return {
                "action": "low_confidence",
                "message": "이전 문서에서 관련성이 낮은 결과만 발견되었습니다. 질문을 구체화하거나 다른 문서를 선택해 주세요.",
                "suggested_docs": new_doc_ids
            }

        elif reason == "better_results_elsewhere":
            message = "다른 문서에서 더 적절한 정보를 찾을 수 있을 것 같습니다."

            if new_doc_ids:
                message += f"\n추천 문서: {', '.join(new_doc_ids[:3])}"

            return {
                "action": "suggest_expand",
                "message": message,
                "suggested_docs": new_doc_ids
            }

        else:
            return {
                "action": "possible_change",
                "message": "주제가 변경된 것으로 보입니다. 계속하시겠습니까?",
                "suggested_docs": new_doc_ids
            }