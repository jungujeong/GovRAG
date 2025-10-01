"""
IDF Statistics Module - NO HARDCODING
Calculates corpus-wide statistics for function word detection
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Dict, List, Set
import logging

logger = logging.getLogger(__name__)


class IDFStats:
    """
    Calculate and store IDF (Inverse Document Frequency) statistics.

    Used for statistical function word detection without hardcoding.
    """

    def __init__(self):
        self.doc_count = 0
        self.word_doc_freq: Dict[str, int] = defaultdict(int)  # word -> doc count
        self.idf_scores: Dict[str, float] = {}

    def build_from_index(self, index_reader):
        """
        Build IDF statistics from Whoosh index.

        Args:
            index_reader: Whoosh index reader
        """
        logger.info("Building IDF statistics from index...")

        self.doc_count = index_reader.doc_count_all()

        # Get schema from index (not from reader which might be MultiReader)
        # Whoosh stores text in "text" field, not "content"
        content_fields = ["text", "content"]  # Try both field names

        for fieldname in content_fields:
            try:
                word_count = 0
                for word in index_reader.lexicon(fieldname):
                    # Count documents containing this word
                    doc_freq = index_reader.doc_frequency(fieldname, word)
                    self.word_doc_freq[word] = doc_freq
                    word_count += 1

                logger.info(f"Collected {word_count} unique words from field '{fieldname}'")
                break  # Successfully processed, stop trying other fields
            except Exception as e:
                logger.debug(f"Field '{fieldname}' not found or error: {e}")
                continue

        # Calculate IDF scores
        self._calculate_idf()

        logger.info(
            f"IDF statistics built: {self.doc_count} docs, "
            f"{len(self.word_doc_freq)} unique words"
        )

    def build_from_documents(self, documents: List[str]):
        """
        Build IDF statistics from document list.

        Args:
            documents: List of document texts
        """
        logger.info(f"Building IDF statistics from {len(documents)} documents...")

        self.doc_count = len(documents)

        for doc in documents:
            # Extract Korean words
            words = set(re.findall(r'[가-힣]{2,}', doc))

            for word in words:
                self.word_doc_freq[word] += 1

        # Calculate IDF scores
        self._calculate_idf()

        logger.info(
            f"IDF statistics built: {self.doc_count} docs, "
            f"{len(self.word_doc_freq)} unique words"
        )

    def _calculate_idf(self):
        """Calculate IDF scores for all words"""
        if self.doc_count == 0:
            return

        for word, doc_freq in self.word_doc_freq.items():
            # IDF = log(N / df)
            # Add smoothing to avoid log(0)
            idf = math.log((self.doc_count + 1) / (doc_freq + 1))
            self.idf_scores[word] = idf

    def get_idf(self, word: str, default: float = 5.0) -> float:
        """
        Get IDF score for a word.

        Args:
            word: The word to look up
            default: Default score for unseen words (high = rare = content word)

        Returns:
            IDF score (higher = rarer = more likely content word)
        """
        return self.idf_scores.get(word, default)

    def is_likely_function_word(
        self,
        word: str,
        threshold: float = 2.0
    ) -> bool:
        """
        Determine if word is likely a function word based on IDF.

        Args:
            word: The word to check
            threshold: IDF threshold (lower = more common = function word)

        Returns:
            True if likely function word, False if likely content word
        """
        idf = self.get_idf(word)
        return idf < threshold

    def get_top_function_words(self, k: int = 100) -> List[tuple]:
        """
        Get top k most common words (likely function words).

        Args:
            k: Number of words to return

        Returns:
            List of (word, idf_score) tuples, sorted by IDF (ascending)
        """
        sorted_words = sorted(
            self.idf_scores.items(),
            key=lambda x: x[1]
        )
        return sorted_words[:k]

    def get_top_content_words(self, k: int = 100) -> List[tuple]:
        """
        Get top k rarest words (likely content words).

        Args:
            k: Number of words to return

        Returns:
            List of (word, idf_score) tuples, sorted by IDF (descending)
        """
        sorted_words = sorted(
            self.idf_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return sorted_words[:k]

    def summarize(self) -> Dict[str, any]:
        """Get summary statistics"""
        if not self.idf_scores:
            return {
                "doc_count": 0,
                "vocab_size": 0,
                "avg_idf": 0.0,
                "median_idf": 0.0,
            }

        idf_values = sorted(self.idf_scores.values())

        return {
            "doc_count": self.doc_count,
            "vocab_size": len(self.idf_scores),
            "avg_idf": sum(idf_values) / len(idf_values),
            "median_idf": idf_values[len(idf_values) // 2],
            "min_idf": idf_values[0],
            "max_idf": idf_values[-1],
        }


class StatisticalFunctionWordFilter:
    """
    Filter function words using statistical methods - NO HARDCODING.

    Uses:
    1. IDF scores (rare words = content words)
    2. Character entropy (diverse characters = content words)
    3. Length statistics (Korean: function words ~2 chars, content words ~3.5 chars)
    """

    def __init__(self, idf_stats: IDFStats):
        self.idf_stats = idf_stats

    def is_content_word(
        self,
        word: str,
        idf_threshold: float = 2.5,
        entropy_threshold: float = 1.5,
        strict: bool = False,
    ) -> bool:
        """
        Determine if word is a content word using STATISTICAL methods only.

        Args:
            word: The word to check
            idf_threshold: IDF threshold (higher = stricter)
            entropy_threshold: Entropy threshold
            strict: If True, apply stricter criteria

        Returns:
            True if content word, False if function word
        """
        # Length-based pre-filter (statistical observation)
        if len(word) < 2:
            return False

        # Very long words are almost always content words
        if len(word) >= 5:
            return True

        # Get IDF score (corpus statistics)
        idf = self.idf_stats.get_idf(word)

        # Calculate character entropy (diversity measure)
        entropy = self._char_entropy(word)

        # Length 2: conservative (likely function words)
        if len(word) == 2:
            if strict:
                return idf > 4.0 and entropy > 1.8  # Very strict
            return idf > 3.5 and entropy > 1.6

        # Length 3: boundary case
        if len(word) == 3:
            if strict:
                return idf > idf_threshold and entropy > entropy_threshold
            # Relaxed: either high IDF or high entropy
            return idf > idf_threshold or entropy > entropy_threshold

        # Length 4+: almost always content words
        return idf > 1.5  # Very relaxed threshold

    def _char_entropy(self, word: str) -> float:
        """
        Calculate character entropy (Shannon entropy).

        Higher entropy = more diverse characters = more likely content word

        Examples:
        - "그래서": 3 chars, 3 unique → high entropy
        - "있습니다": 4 chars, 4 unique → high entropy
        - "정월대보름": 5 chars, 5 unique → high entropy
        - "다다다": 3 chars, 1 unique → low entropy
        """
        from collections import Counter

        char_counts = Counter(word)
        total = len(word)

        if total <= 1:
            return 0.0

        entropy = -sum(
            (count / total) * math.log2(count / total)
            for count in char_counts.values()
        )

        return entropy

    def filter_words(
        self,
        words: List[str],
        **kwargs
    ) -> List[str]:
        """
        Filter list of words, keeping only content words.

        Args:
            words: List of words to filter
            **kwargs: Arguments passed to is_content_word()

        Returns:
            Filtered list of content words
        """
        return [
            word for word in words
            if self.is_content_word(word, **kwargs)
        ]


# Global instance (lazy-initialized)
_global_idf_stats: IDFStats | None = None
_global_filter: StatisticalFunctionWordFilter | None = None


def get_global_idf_stats() -> IDFStats:
    """Get or create global IDF stats instance"""
    global _global_idf_stats
    if _global_idf_stats is None:
        _global_idf_stats = IDFStats()
        # Will be built from index on first use
    return _global_idf_stats


def get_global_filter() -> StatisticalFunctionWordFilter:
    """Get or create global filter instance"""
    global _global_filter
    if _global_filter is None:
        idf_stats = get_global_idf_stats()
        _global_filter = StatisticalFunctionWordFilter(idf_stats)
    return _global_filter


def build_global_idf_stats(index):
    """
    Build global IDF statistics from Whoosh index.

    This should be called once at startup in main.py lifespan.

    Args:
        index: Whoosh Index instance
    """
    global _global_idf_stats, _global_filter

    logger.info("[IDF] Building global IDF statistics from index...")
    stats = IDFStats()

    with index.reader() as reader:
        stats.build_from_index(reader)

    _global_idf_stats = stats
    _global_filter = StatisticalFunctionWordFilter(stats)

    logger.info(f"[IDF] Global IDF statistics built: {stats.summarize()}")
    logger.info("[IDF] Global filter ready")
