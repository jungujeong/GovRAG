"""
Template-Based Evidence Extractor - ZERO HALLUCINATION

Evidence에서 직접 추출만 하고, LLM 생성 없음.
100% Evidence 단어만 사용하여 할루시네이션 방지.
"""

from typing import List, Dict, Tuple
import re
from rag.fuzzy_matcher import get_fuzzy_matcher
from rag.korean_analyzer import get_korean_analyzer
import logging

logger = logging.getLogger(__name__)


class TemplateExtractor:
    """
    Template-based evidence extraction

    LLM 생성 대신 Evidence에서 직접 추출:
    1. Query와 매칭되는 문장 찾기 (Fuzzy Matching)
    2. 점수순 정렬
    3. Template 조합 (Evidence 원문 그대로)

    장점:
    - Jaccard similarity 1.0 (100% Evidence 사용)
    - 할루시네이션 불가능
    - 조사 변형 없음 (원문 그대로)
    """

    def __init__(self, match_threshold: float = 0.15):
        """
        Args:
            match_threshold: 최소 유사도 (기본 0.15)
        """
        self.fuzzy_matcher = get_fuzzy_matcher()
        self.korean_analyzer = get_korean_analyzer()
        self.match_threshold = match_threshold

    def extract(
        self,
        query: str,
        evidences: List[Dict]
    ) -> Dict:
        """
        Extract evidence-only answer

        Args:
            query: 검색 질의
            evidences: Evidence 리스트

        Returns:
            {
                "answer": str,
                "sources": List[Dict],
                "metadata": Dict
            }
        """
        logger.debug(f"Template Extractor: query='{query}', evidences={len(evidences)}")

        # 1. Query와 매칭되는 문장 찾기
        matched_sentences = self._find_matched_sentences(query, evidences)

        logger.debug(f"Found {len(matched_sentences)} matched sentences")

        # 2. 매칭된 문장이 없으면 no-answer template
        if not matched_sentences:
            return self._no_answer_template(evidences)

        # 3. Template 조합 (상위 N개만)
        answer = self._assemble_template(matched_sentences, top_k=3)

        # 4. Sources 생성 (Evidence 그대로)
        sources = self._create_sources(matched_sentences, evidences)

        # 5. Metadata
        metadata = {
            "extraction_method": "template",
            "matched_sentences": len(matched_sentences),
            "used_evidences": len(set(m["evidence_idx"] for m in matched_sentences)),
            "jaccard_expected": 1.0,
            "hallucination_risk": 0.0
        }

        return {
            "answer": answer,
            "sources": sources,
            "metadata": metadata
        }

    def _find_matched_sentences(
        self,
        query: str,
        evidences: List[Dict]
    ) -> List[Dict]:
        """
        Find sentences in evidences that match the query

        Uses hybrid matching:
        1. Fuzzy similarity (n-gram, Levenshtein)
        2. Keyword overlap (content words)

        Args:
            query: Search query
            evidences: List of evidence dictionaries

        Returns:
            List of matched sentence dictionaries with scores
        """
        matched = []

        # Extract query keywords
        query_keywords = set(self.korean_analyzer.analyze(query))

        for ev_idx, evidence in enumerate(evidences):
            text = evidence.get("text", "")

            # Split into sentences
            sentences = self._split_sentences(text)

            for sent_idx, sentence in enumerate(sentences):
                # 1. Fuzzy similarity score
                fuzzy_score = self.fuzzy_matcher.combined_similarity(query, sentence)

                # 2. Keyword overlap score
                sentence_keywords = set(self.korean_analyzer.analyze(sentence))
                if len(query_keywords) > 0:
                    overlap = len(query_keywords & sentence_keywords)
                    keyword_score = overlap / len(query_keywords)
                else:
                    keyword_score = 0.0

                # 3. Combined score (weighted average)
                combined_score = (fuzzy_score * 0.4) + (keyword_score * 0.6)

                if combined_score >= self.match_threshold:
                    matched.append({
                        "text": sentence,
                        "score": combined_score,
                        "fuzzy_score": fuzzy_score,
                        "keyword_score": keyword_score,
                        "evidence_idx": ev_idx,
                        "sentence_idx": sent_idx,
                        "doc_id": evidence.get("doc_id", ""),
                        "page": evidence.get("page", 0),
                        "citation": ev_idx + 1
                    })

        # Sort by score (descending)
        matched.sort(key=lambda x: x["score"], reverse=True)

        logger.debug(f"Matched {len(matched)} sentences with query keywords: {query_keywords}")

        return matched

    def _split_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences

        Args:
            text: Input text

        Returns:
            List of sentences
        """
        # Korean sentence endings: 다, 요, 음, 까, 지, etc.
        # Also split by newlines
        sentences = re.split(r'[.!?\n]+', text)

        # Clean and filter
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]

        return sentences

    def _assemble_template(
        self,
        matched_sentences: List[Dict],
        top_k: int = 3
    ) -> str:
        """
        Assemble answer from matched sentences

        Args:
            matched_sentences: Matched sentence dictionaries
            top_k: Number of top sentences to include

        Returns:
            Assembled answer text
        """
        # Take top K sentences
        top_sentences = matched_sentences[:top_k]

        # Template header
        answer = "📄 문서 내용:\n\n"

        # Add each matched sentence
        for match in top_sentences:
            answer += f"• {match['text']} [{match['citation']}]\n\n"

        return answer.strip()

    def _create_sources(
        self,
        matched_sentences: List[Dict],
        evidences: List[Dict]
    ) -> List[Dict]:
        """
        Create sources from matched sentences

        Args:
            matched_sentences: Matched sentence dictionaries
            evidences: Original evidence list

        Returns:
            List of source dictionaries
        """
        # Get unique evidence indices used
        used_evidence_indices = sorted(set(m["evidence_idx"] for m in matched_sentences))

        sources = []
        for idx in used_evidence_indices:
            evidence = evidences[idx]
            sources.append({
                "index": idx + 1,
                "citation_number": idx + 1,
                "doc_id": evidence.get("doc_id", ""),
                "page": evidence.get("page", 0),
                "start_char": evidence.get("start_char", 0),
                "end_char": evidence.get("end_char", 0),
                "text_snippet": evidence.get("text", "")[:200],
                "score": evidence.get("score", 0.0)
            })

        return sources

    def _no_answer_template(self, evidences: List[Dict]) -> Dict:
        """
        No-answer template when no matches found

        Args:
            evidences: Evidence list (for metadata)

        Returns:
            No-answer response dictionary
        """
        answer = (
            "💬 제공된 문서에서 관련 정보를 찾을 수 없습니다.\n\n"
            "질문을 다시 작성하시거나, 구체적인 키워드를 포함해 주세요."
        )

        # Still provide all evidences as sources for transparency
        sources = []
        for idx, evidence in enumerate(evidences):
            sources.append({
                "index": idx + 1,
                "citation_number": idx + 1,
                "doc_id": evidence.get("doc_id", ""),
                "page": evidence.get("page", 0),
                "start_char": evidence.get("start_char", 0),
                "end_char": evidence.get("end_char", 0),
                "text_snippet": evidence.get("text", "")[:200],
                "score": evidence.get("score", 0.0)
            })

        metadata = {
            "extraction_method": "no_match",
            "matched_sentences": 0,
            "used_evidences": 0,
            "jaccard_expected": 0.0,
            "hallucination_risk": 0.0
        }

        return {
            "answer": answer,
            "sources": sources,
            "metadata": metadata
        }


# Global instance
_template_extractor_instance = None


def get_template_extractor() -> TemplateExtractor:
    """Get global template extractor instance"""
    global _template_extractor_instance
    if _template_extractor_instance is None:
        _template_extractor_instance = TemplateExtractor()
    return _template_extractor_instance
