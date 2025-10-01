"""
Fuzzy Matcher for Korean Text - ZERO HEURISTICS

인덱스된 문서와 query를 직접 비교하여 매칭합니다.
패턴/조사 하드코딩 없이 순수 문자열 유사도만 사용합니다.
"""

from typing import List, Tuple
import re


class FuzzyMatcher:
    """
    패턴 없는 한국어 텍스트 매칭

    원리:
    1. n-gram 생성 (문자 단위)
    2. Jaccard similarity 계산
    3. 최소 편집 거리 (Levenshtein) 계산

    하드코딩 없음! 모든 한국어에 동작합니다.
    """

    def __init__(self, ngram_size: int = 3):
        """
        Args:
            ngram_size: n-gram 크기 (기본 3)
        """
        self.ngram_size = ngram_size

    def create_ngrams(self, text: str) -> set:
        """
        문자 단위 n-gram 생성

        Example:
            create_ngrams("정월대보름")
            → {"정월대", "월대보", "대보름"}

        Args:
            text: 입력 텍스트

        Returns:
            n-gram 집합
        """
        # 공백 제거
        text = text.replace(" ", "")

        if len(text) < self.ngram_size:
            return {text}

        ngrams = set()
        for i in range(len(text) - self.ngram_size + 1):
            ngrams.add(text[i:i + self.ngram_size])

        return ngrams

    def jaccard_similarity(self, text1: str, text2: str) -> float:
        """
        Jaccard similarity 계산 (n-gram 기반)

        Example:
            jaccard("정월대보름에", "정월대보름")
            → 0.83  (높은 유사도)

        Args:
            text1, text2: 비교할 텍스트

        Returns:
            0.0 ~ 1.0 사이의 유사도
        """
        ngrams1 = self.create_ngrams(text1)
        ngrams2 = self.create_ngrams(text2)

        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = ngrams1 & ngrams2
        union = ngrams1 | ngrams2

        return len(intersection) / len(union)

    def levenshtein_distance(self, text1: str, text2: str) -> int:
        """
        Levenshtein 편집 거리 계산

        Example:
            levenshtein("정월대보름에", "정월대보름")
            → 1  (1글자 차이)

        Args:
            text1, text2: 비교할 텍스트

        Returns:
            편집 거리 (0 = 동일)
        """
        # 공백 제거
        text1 = text1.replace(" ", "")
        text2 = text2.replace(" ", "")

        if text1 == text2:
            return 0

        len1, len2 = len(text1), len(text2)

        # DP 테이블
        dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]

        # 초기화
        for i in range(len1 + 1):
            dp[i][0] = i
        for j in range(len2 + 1):
            dp[0][j] = j

        # 편집 거리 계산
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if text1[i-1] == text2[j-1]:
                    dp[i][j] = dp[i-1][j-1]
                else:
                    dp[i][j] = min(
                        dp[i-1][j] + 1,      # 삭제
                        dp[i][j-1] + 1,      # 삽입
                        dp[i-1][j-1] + 1     # 치환
                    )

        return dp[len1][len2]

    def normalized_levenshtein(self, text1: str, text2: str) -> float:
        """
        정규화된 Levenshtein 거리 (0.0 ~ 1.0)

        Args:
            text1, text2: 비교할 텍스트

        Returns:
            유사도 (1.0 = 동일, 0.0 = 완전 다름)
        """
        distance = self.levenshtein_distance(text1, text2)
        max_len = max(len(text1), len(text2))

        if max_len == 0:
            return 1.0

        return 1.0 - (distance / max_len)

    def combined_similarity(self, text1: str, text2: str) -> float:
        """
        결합 유사도 (Jaccard + Levenshtein)

        Args:
            text1, text2: 비교할 텍스트

        Returns:
            0.0 ~ 1.0 사이의 유사도
        """
        jaccard = self.jaccard_similarity(text1, text2)
        levenshtein = self.normalized_levenshtein(text1, text2)

        # 평균
        return (jaccard + levenshtein) / 2.0

    def find_best_match(
        self,
        query: str,
        candidates: List[str],
        threshold: float = 0.5
    ) -> List[Tuple[str, float]]:
        """
        Query와 가장 유사한 candidate 찾기

        Example:
            query = "정월대보름에 대해"
            candidates = ["정월대보름 관련 내용", "홍티예술촌", "사하구"]
            → [("정월대보름 관련 내용", 0.85)]

        Args:
            query: 검색 질의
            candidates: 후보 텍스트 리스트
            threshold: 최소 유사도 (기본 0.5)

        Returns:
            (candidate, similarity) 튜플 리스트 (정렬됨)
        """
        matches = []

        for candidate in candidates:
            similarity = self.combined_similarity(query, candidate)

            if similarity >= threshold:
                matches.append((candidate, similarity))

        # 유사도 내림차순 정렬
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches

    def substring_match(self, query: str, text: str, min_length: int = 3) -> float:
        """
        최대 공통 부분 문자열 비율

        Example:
            query = "정월대보름"
            text = "정월대보름 행사 개최"
            → 1.0 (query가 text에 완전히 포함됨)

        Args:
            query: 검색어
            text: 대상 텍스트
            min_length: 최소 매칭 길이

        Returns:
            0.0 ~ 1.0 비율
        """
        # 공백 제거
        query = query.replace(" ", "")
        text = text.replace(" ", "")

        # Query가 text에 포함되면 1.0
        if query in text:
            return 1.0

        # 최대 공통 부분 문자열 찾기
        max_match_len = 0

        for i in range(len(query)):
            for j in range(i + min_length, len(query) + 1):
                substring = query[i:j]
                if substring in text:
                    max_match_len = max(max_match_len, len(substring))

        if max_match_len == 0:
            return 0.0

        return max_match_len / len(query)


# Global instance
_fuzzy_matcher_instance = None


def get_fuzzy_matcher() -> FuzzyMatcher:
    """Get global fuzzy matcher instance"""
    global _fuzzy_matcher_instance
    if _fuzzy_matcher_instance is None:
        _fuzzy_matcher_instance = FuzzyMatcher()
    return _fuzzy_matcher_instance
