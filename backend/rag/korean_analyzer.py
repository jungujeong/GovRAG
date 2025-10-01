"""
Korean Morphological Analyzer for Universal RAG

자동으로 조사를 제거하고 content words만 추출합니다.
모든 한국어 질문에 대해 동일하게 작동합니다.
"""

from konlpy.tag import Mecab
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class KoreanAnalyzer:
    """
    한국어 형태소 분석기

    기능:
    1. 조사 자동 제거 ("정월대보름에" → "정월대보름")
    2. Content words만 추출 (명사, 동사, 형용사)
    3. 형태소 기반 검색어 생성

    Example:
        >>> analyzer = KoreanAnalyzer()
        >>> analyzer.analyze("정월대보름에 관련된 지시사항을 알려줘")
        ['정월대보름', '관련', '지시사항', '알리다']
    """

    # Content word POS tags (명사, 동사, 형용사, 관형사, 부사)
    CONTENT_POS_PREFIXES = ('N', 'V', 'M', 'J')

    # Stop words (너무 일반적인 단어들 - 검색 노이즈)
    STOP_WORDS = {
        '있다', '없다', '하다', '되다', '이다', '아니다',
        '것', '수', '등', '및', '또', '또는', '그리고',
        '대', '에', '의', '를', '을', '가', '이', '는', '은'
    }

    def __init__(self):
        """Initialize Mecab morphological analyzer"""
        try:
            self.mecab = Mecab()
            logger.info("Korean analyzer initialized with Mecab")
        except Exception as e:
            logger.error(f"Failed to initialize Mecab: {e}")
            logger.warning("Falling back to simple word splitting")
            self.mecab = None

    def analyze(self, text: str) -> List[str]:
        """
        Analyze Korean text and extract content words

        Args:
            text: Input Korean text

        Returns:
            List of content words (조사 제거, stopwords 제외)

        Example:
            >>> analyze("정월대보름에 대해 알려줘")
            ['정월대보름', '알리다']
        """
        if not text or not text.strip():
            return []

        if self.mecab is None:
            # Fallback: simple word splitting
            return self._simple_analyze(text)

        try:
            # Morphological analysis
            morphs = self.mecab.pos(text)
            content_words = []

            for word, pos in morphs:
                # Skip stop words
                if word in self.STOP_WORDS:
                    continue

                # Extract content words only
                if any(pos.startswith(prefix) for prefix in self.CONTENT_POS_PREFIXES):
                    # 너무 짧은 단어 제외 (1글자)
                    if len(word) > 1:
                        content_words.append(word)

            logger.debug(f"Analyzed '{text[:50]}...' → {content_words}")
            return content_words

        except Exception as e:
            logger.error(f"Mecab analysis failed: {e}, falling back to simple analysis")
            return self._simple_analyze(text)

    def _simple_analyze(self, text: str) -> List[str]:
        """
        Fallback: simple Korean word extraction with particle removal

        Uses regex-based particle stripping - works without Mecab!

        Args:
            text: Input text

        Returns:
            List of Korean words with particles removed
        """
        import re

        # Extract Korean words (2+ chars)
        words = re.findall(r'[가-힣]{2,}', text)

        # Remove common particles using regex
        cleaned_words = []
        for word in words:
            # Remove particles at end
            cleaned = self._remove_particles(word)

            # Remove stop words
            if cleaned not in self.STOP_WORDS and len(cleaned) >= 2:
                cleaned_words.append(cleaned)

        return cleaned_words

    def _remove_particles(self, word: str) -> str:
        """
        Remove Korean particles from word endings

        Common particles:
        - 이/가 (subject)
        - 을/를 (object)
        - 은/는 (topic)
        - 에/에서/에게 (location/direction)
        - 의 (possessive)
        - 과/와/하고 (and)

        Example:
            "정월대보름에" → "정월대보름"
            "지시사항을" → "지시사항"
            "사하구에서" → "사하구"
        """
        import re

        # Regex pattern for common particles
        # Ordered by specificity (longer patterns first)
        particle_patterns = [
            r'(에서|에게|으로|으로서|부터|까지|마저|조차|밖에|에도|에만)$',  # 2-char particles
            r'(이|가|을|를|은|는|의|와|과|도|만|에|서)$',  # 1-char particles
        ]

        for pattern in particle_patterns:
            word = re.sub(pattern, '', word)

        return word

    def analyze_with_pos(self, text: str) -> List[Tuple[str, str]]:
        """
        Analyze with POS tags (for debugging/inspection)

        Args:
            text: Input Korean text

        Returns:
            List of (word, pos_tag) tuples

        Example:
            >>> analyze_with_pos("정월대보름에 대해")
            [('정월대보름', 'NNG'), ('대하', 'VV')]
        """
        if self.mecab is None:
            return [(w, 'UNKNOWN') for w in self._simple_analyze(text)]

        try:
            morphs = self.mecab.pos(text)
            return [
                (word, pos) for word, pos in morphs
                if word not in self.STOP_WORDS
                and any(pos.startswith(p) for p in self.CONTENT_POS_PREFIXES)
            ]
        except Exception as e:
            logger.error(f"POS analysis failed: {e}")
            return [(w, 'ERROR') for w in self._simple_analyze(text)]

    def create_search_query(self, text: str) -> str:
        """
        Create optimized search query from Korean text

        Args:
            text: Input Korean text

        Returns:
            Space-separated content words for BM25 search

        Example:
            >>> create_search_query("정월대보름에 관련된 지시사항을 알려줘")
            "정월대보름 관련 지시사항 알리다"
        """
        content_words = self.analyze(text)
        return " ".join(content_words)


# Global instance (singleton pattern)
_analyzer_instance = None


def get_korean_analyzer() -> KoreanAnalyzer:
    """
    Get global Korean analyzer instance (singleton)

    Returns:
        KoreanAnalyzer instance
    """
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = KoreanAnalyzer()
    return _analyzer_instance
