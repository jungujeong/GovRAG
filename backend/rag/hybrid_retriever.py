from typing import List, Dict, Optional, Tuple
import numpy as np
from collections import defaultdict
import logging
import re
import unicodedata
from rapidfuzz import fuzz

from config import config
from rag.whoosh_bm25 import WhooshBM25
from rag.chroma_store import ChromaStore
from rag.embedder import Embedder
from processors.normalizer_govkr import NormalizerGovKR

logger = logging.getLogger(__name__)

class HybridRetriever:
    """Hybrid retriever combining BM25 and vector search with RRF"""
    
    def __init__(self):
        self.bm25 = WhooshBM25()
        self.chroma = ChromaStore()
        self.embedder = Embedder()
        self.normalizer = NormalizerGovKR()
        
        # RRF parameter
        self.rrf_k = config.RRF_K
        
        # Search weights
        self.w_bm25 = config.W_BM25
        self.w_vector = config.W_VECTOR
        self.w_rerank = config.W_RERANK
    
    def retrieve(self, query: str, limit: int = 10, document_ids: Optional[List[str]] = None) -> List[Dict]:
        """Retrieve documents using hybrid search with optional document filtering"""
        # Normalize query
        normalized_query = self.normalizer.normalize_query(query)

        # Extract keywords for logging
        query_keywords = self._extract_keywords(query)
        self._last_keywords = query_keywords  # Store for logging

        # BM25 search
        bm25_results = self._bm25_search(normalized_query, document_ids)
        self._last_bm25_count = len(bm25_results)  # Store for logging

        # Vector search
        vector_results = self._vector_search(query, document_ids)  # Use original query for embedding
        self._last_vector_count = len(vector_results)  # Store for logging

        # Combine with RRF
        combined_results = self._reciprocal_rank_fusion(
            bm25_results,
            vector_results
        )
        self._last_rrf_count = len(combined_results)  # Store for logging

        # Filter by relevance
        filtered_results = self._filter_by_relevance(query, combined_results)
        self._last_filtered_count = len(filtered_results)  # Store for logging

        # Ensure diverse document coverage
        diverse_results = self._ensure_document_diversity(filtered_results, limit)

        # Store include_reason in results for logging
        for result in diverse_results:
            if "include_reason" not in result:
                result["include_reason"] = "diversity_selection"

        # Return top results
        return diverse_results
    
    def _bm25_search(self, query: str, document_ids: Optional[List[str]] = None) -> List[Dict]:
        """Perform BM25 search with optional document filtering"""
        try:
            # Get more results initially to ensure we capture all documents
            # When filtering by document_ids, get more results to ensure we find mentions in all docs
            search_limit = config.TOPK_BM25 * 3 if document_ids else config.TOPK_BM25 * 2
            results = self.bm25.search(query, limit=search_limit)

            # Filter by document IDs if provided
            if document_ids:
                # Normalize Unicode for comparison (handle NFD vs NFC)
                normalized_doc_ids = set(unicodedata.normalize('NFC', doc_id) for doc_id in document_ids)

                # Log for debugging
                logger.debug(f"Filter doc IDs (normalized): {normalized_doc_ids}")
                logger.debug(f"First 3 result doc IDs: {[r.get('doc_id', '') for r in results[:3]]}")

                filtered_results = []
                for r in results:
                    result_doc_id = unicodedata.normalize('NFC', r.get("doc_id", ""))
                    if result_doc_id in normalized_doc_ids:
                        filtered_results.append(r)

                logger.info(f"BM25 filtering: {len(results)} -> {len(filtered_results)} results")
                results = filtered_results
            
            # Normalize BM25 scores
            if results:
                max_score = max(r["score"] for r in results)
                if max_score > 0:
                    for r in results:
                        r["normalized_score"] = r["score"] / max_score
                else:
                    for r in results:
                        r["normalized_score"] = 0.0
            
            logger.info(f"BM25 returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []
    
    def _vector_search(self, query: str, document_ids: Optional[List[str]] = None) -> List[Dict]:
        """Perform vector similarity search with optional document filtering"""
        try:
            # Generate query embedding
            query_embedding = self.embedder.encode_query(query)

            # Search in ChromaDB - get more results to ensure comprehensive coverage
            results = self.chroma.search(
                query_embedding.tolist(),
                limit=config.TOPK_VECTOR * 3 if document_ids else config.TOPK_VECTOR * 2
            )

            # Filter by document IDs if provided
            if document_ids:
                # Normalize Unicode for comparison (handle NFD vs NFC)
                normalized_doc_ids = set(unicodedata.normalize('NFC', doc_id) for doc_id in document_ids)

                filtered_results = []
                for r in results:
                    result_doc_id = unicodedata.normalize('NFC', r.get("doc_id", ""))
                    if result_doc_id in normalized_doc_ids:
                        filtered_results.append(r)

                logger.info(f"Vector filtering: {len(results)} -> {len(filtered_results)} results")
                results = filtered_results[:config.TOPK_VECTOR]
            
            # Scores from ChromaDB are already normalized (cosine similarity)
            for r in results:
                r["normalized_score"] = r["score"]
            
            logger.info(f"Vector search returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def _reciprocal_rank_fusion(self, 
                                bm25_results: List[Dict],
                                vector_results: List[Dict]) -> List[Dict]:
        """Combine results using Reciprocal Rank Fusion"""
        
        # Create score dictionaries
        rrf_scores = defaultdict(float)
        chunk_data = {}
        
        # Process BM25 results
        for rank, result in enumerate(bm25_results, 1):
            chunk_id = result["chunk_id"]
            # RRF score formula
            rrf_scores[chunk_id] += self.w_bm25 * (1.0 / (self.rrf_k + rank))
            chunk_data[chunk_id] = result
        
        # Process vector results
        for rank, result in enumerate(vector_results, 1):
            chunk_id = result["chunk_id"]
            rrf_scores[chunk_id] += self.w_vector * (1.0 / (self.rrf_k + rank))
            # Update chunk data if not already present
            if chunk_id not in chunk_data:
                chunk_data[chunk_id] = result
        
        # Create combined results
        combined_results = []
        for chunk_id, rrf_score in rrf_scores.items():
            result = chunk_data[chunk_id].copy()
            result["rrf_score"] = rrf_score
            result["hybrid_score"] = rrf_score  # Can be modified with reranking
            combined_results.append(result)
        
        # Sort by RRF score
        combined_results.sort(key=lambda x: x["rrf_score"], reverse=True)
        
        logger.info(f"RRF fusion produced {len(combined_results)} results")
        
        return combined_results
    
    def retrieve_with_filters(self, 
                             query: str,
                             doc_ids: Optional[List[str]] = None,
                             doc_types: Optional[List[str]] = None,
                             limit: int = 10) -> List[Dict]:
        """Retrieve with document filters"""
        # Get base results
        results = self.retrieve(query, limit=limit * 2)  # Get more to account for filtering
        
        # Apply filters
        filtered_results = []
        for result in results:
            # Filter by document IDs
            if doc_ids and result.get("doc_id") not in doc_ids:
                continue
            
            # Filter by document types
            if doc_types and result.get("type") not in doc_types:
                continue
            
            filtered_results.append(result)
            
            if len(filtered_results) >= limit:
                break
        
        logger.info(f"Filtered retrieval returned {len(filtered_results)} results")
        return filtered_results
    
    def get_similar_chunks(self, chunk_id: str, limit: int = 5) -> List[Dict]:
        """Get chunks similar to a given chunk"""
        # Get the chunk
        chunk = self.chroma.get_chunk(chunk_id)
        
        if not chunk:
            logger.warning(f"Chunk not found: {chunk_id}")
            return []
        
        # Get embedding for the chunk text
        embedding = self.embedder.embed_text(chunk["text"])
        
        # Search for similar chunks
        results = self.chroma.search(embedding.tolist(), limit=limit + 1)
        
        # Remove the query chunk itself
        results = [r for r in results if r["chunk_id"] != chunk_id]
        
        return results[:limit]
    
    def _filter_by_relevance(self, query: str, results: List[Dict],
                           min_score: float = 0.03,  # Trust RRF score (already combines BM25+Vector)
                           keyword_threshold: float = 0.12) -> List[Dict]:  # Minimal threshold - trust semantic search
        """Filter results primarily by RRF score (semantic+keyword combined), not keyword-only"""
        if not results:
            logger.warning("No results to filter")
            return []

        logger.info(f"Starting relevance filtering with {len(results)} results")

        # Extract query keywords
        query_keywords = self._extract_keywords(query)
        logger.info(f"Extracted keywords: {query_keywords}")

        filtered_results = []
        debug_info = []

        for i, result in enumerate(results):
            rrf_score = result.get("rrf_score", 0)
            text = result.get("text", "")

            if not text:
                debug_info.append(f"Result {i}: No text content")
                continue

            # Calculate keyword relevance
            keyword_relevance = self._calculate_keyword_relevance(query_keywords, text)
            result["keyword_relevance"] = keyword_relevance

            # Balanced filtering - trust both signals with appropriate thresholds
            include_reason = None

            # Debug logging for first few results
            if i < 10:
                logger.info(f"[FILTER_DEBUG] Result {i}: rrf={rrf_score:.4f}, kw={keyword_relevance:.3f}, doc={result.get('doc_id')}")

            # Strict filtering strategy: Require BOTH signals
            # This prevents irrelevant documents with high RRF but no keyword match
            if rrf_score >= 0.006 and keyword_relevance >= 0.15:
                # Strong semantic match WITH keyword presence - most reliable
                include_reason = f"hybrid={rrf_score:.4f}_kw={keyword_relevance:.3f}"
            elif keyword_relevance >= 0.30:
                # Very strong keyword match (query term prominently mentioned)
                # Raised from 0.25 to 0.30 to be more selective
                include_reason = f"strong_keyword={keyword_relevance:.3f}"
            # Removed: elif rrf_score >= 0.010 (too permissive without keyword evidence)

            # Note: Removed single-condition logic - require evidence from both signals

            if include_reason:
                filtered_results.append(result)
                debug_info.append(f"Result {i}: INCLUDED - {include_reason}")
            else:
                debug_info.append(f"Result {i}: FILTERED - rrf={rrf_score:.3f}, kw={keyword_relevance:.3f}")
        
        # If still no results, apply very conservative emergency fallback
        if not filtered_results and len(results) > 0:
            logger.warning("No results passed filtering, applying emergency fallback")
            # Take top 2 results by RRF score (conservative but not too restrictive)
            emergency_results = sorted(results, key=lambda x: x.get("rrf_score", 0), reverse=True)[:2]
            for result in emergency_results:
                if "keyword_relevance" not in result:
                    result["keyword_relevance"] = self._calculate_keyword_relevance(query_keywords, result.get("text", ""))
                # Mark as emergency fallback
                result["include_reason"] = f"emergency_fallback_rrf={result.get('rrf_score', 0):.3f}"
            filtered_results = emergency_results
            logger.warning(f"Emergency fallback: included {len(filtered_results)} top results (may not be highly relevant)")
        
        # Sort by combined relevance
        filtered_results.sort(key=lambda x: (
            x.get("rrf_score", 0) * 0.7 + x.get("keyword_relevance", 0) * 0.3
        ), reverse=True)
        
        logger.info(f"Relevance filtering: {len(results)} -> {len(filtered_results)} results")
        if logger.isEnabledFor(logging.DEBUG):
            for info in debug_info[:10]:  # Log first 10 for debugging
                logger.debug(info)
        
        return filtered_results
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract meaningful keywords using MORPHOLOGY-BASED approach.

        Data-driven strategy:
        1. Extract all Korean word segments (2+ chars)
        2. Strip grammatical particles
        3. Filter by morphological characteristics (length, structure)
        4. Let BM25 index judge importance via IDF

        No hard-coded domain terms - adapts to any document corpus.
        """
        keywords = []

        # 1. Numbers and structured patterns (universal importance)
        numbers = re.findall(r'\d+(?:년|월|일|호|회|차|번|개|명|건)?', query)
        keywords.extend(numbers)

        # Government document patterns (structural, not content-specific)
        gov_patterns = re.findall(r'제\s*\d+\s*[호조항차회]', query)
        keywords.extend(gov_patterns)

        # 2. Korean words - extract all potential content words
        korean_words = re.findall(r'[가-힣]{2,}', query)

        for word in korean_words:
            # NO particle stripping - BM25's TF-IDF handles it automatically
            # Statistical approach: Let the search engine down-weight common particles
            if len(word) < 2:
                continue

            # Morphological filtering - no domain knowledge needed
            if self._is_likely_content_word(word):
                keywords.append(word)

        # 3. English/alphanumeric terms
        english_terms = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', query)
        keywords.extend([term for term in english_terms if len(term) >= 2])

        # Remove duplicates, preserve order for debugging
        seen = set()
        unique_keywords = []
        for kw in keywords:
            if kw not in seen:
                seen.add(kw)
                unique_keywords.append(kw)

        logger.info(f"Extracted keywords: {unique_keywords}")
        return unique_keywords

    def _strip_particles(self, word: str) -> str:
        """Strip common Korean particles from end of word"""
        particles = ['은', '는', '이', '가', '을', '를', '에', '의', '도', '만', '와', '과', '로', '서', '부터', '까지', '에서', '에게', '한테', '으로', '라고']
        for particle in sorted(particles, key=len, reverse=True):  # Longer particles first
            if word.endswith(particle) and len(word) > len(particle):
                return word[:-len(particle)]
        return word

    def _is_likely_content_word(self, word: str) -> bool:
        """
        Determine if a Korean word is likely a content word (noun, proper noun)
        using MORPHOLOGICAL features only - no domain knowledge.

        Purely linguistic approach that adapts to any corpus.
        """
        if len(word) < 2:
            return False

        # 1. Length heuristic (strong signal, no domain knowledge)
        #    Longer Korean words are statistically more likely to be content words
        if len(word) >= 4:
            return True  # 홍티예술촌, 감천문화마을, 외국인관광객

        # 2. Reject clear verb/adjective forms (morphology, not semantics)
        verb_adj_endings = [
            '하다', '되다', '이다',  # Basic verb endings
            '하는', '되는', '한다', '된다', '하고', '되고', '이고',  # Conjugated forms
            '하여', '되어', '이어', '하니', '되니'
        ]
        if any(word.endswith(ending) for ending in verb_adj_endings):
            return False

        # 3. Reject standalone particles (grammatical, not content)
        particles = ['은', '는', '이', '가', '을', '를', '에', '의', '도', '만', '와', '과', '로', '서']
        if word in particles:
            return False

        # 4. For 3-char words: Generally accept (statistically likely nouns)
        if len(word) == 3:
            # Reject only extremely common function words
            function_3char = ['그리고', '하지만', '그러나', '또한', '그런데', '따라서', '그래서']
            return word not in function_3char

        # 5. For 2-char words: Use morphological cues
        if len(word) == 2:
            # Check final character for noun-like jongseong (받침)
            # Many Korean nouns end with certain characters
            final_char = word[-1]

            # Common noun endings (linguistic pattern, not domain-specific)
            noun_endings = ['촌', '관', '장', '과', '단', '원', '실', '부', '국', '청', '소', '처', '회', '사', '인']
            if final_char in noun_endings:
                return True

            # Otherwise, 2-char words are too ambiguous - reject to avoid noise
            return False

        return False
    
    def _calculate_keyword_relevance(self, keywords: List[str], text: str) -> float:
        """Calculate keyword relevance score with improved Korean handling"""
        if not keywords:
            return 0.2  # Give some base score even without keywords
        
        text_lower = text.lower()
        query_lower = ' '.join(keywords).lower()
        
        # 1. Exact substring matching (more flexible than word matching)
        exact_matches = 0
        partial_matches = 0
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            if keyword_lower in text_lower:
                exact_matches += 1
            else:
                # Check for partial matches (keyword contains or is contained)
                if self._has_partial_match(keyword_lower, text_lower):
                    partial_matches += 1
        
        # 2. Calculate base scores
        exact_score = exact_matches / len(keywords) if keywords else 0
        partial_score = partial_matches / len(keywords) if keywords else 0
        
        # 3. Semantic overlap using character n-grams (better for Korean)
        ngram_score = self._calculate_ngram_similarity(query_lower, text_lower)
        
        # 4. Special handling for numbers and government terms
        number_match_score = self._calculate_number_match_score(keywords, text)
        
        # 5. Length bonus for longer queries (assume more specific)
        length_bonus = min(len(' '.join(keywords)) / 20.0, 0.1)  # Max 0.1 bonus
        
        # 6. Combined score with adjusted weights (more permissive)
        total_score = (
            exact_score * 0.4 +           # Exact matches important but not overwhelming
            partial_score * 0.25 +        # Partial matches more valuable
            ngram_score * 0.25 +          # Semantic similarity more valuable
            number_match_score * 0.1 +    # Number/term matching
            length_bonus                  # Bonus for longer, more specific queries
        )
        
        # 7. Ensure minimum score for any text with some similarity
        if ngram_score > 0.05 or partial_matches > 0 or exact_matches > 0:
            total_score = max(total_score, 0.1)  # Minimum relevance score
        
        return min(total_score, 1.0)
    
    def _has_partial_match(self, keyword: str, text: str) -> bool:
        """Check for partial matches in Korean text"""
        # For Korean, check if keyword is substring of any word in text
        # or if any word in text is substring of keyword
        text_words = re.findall(r'[가-힣]+', text)
        
        for word in text_words:
            if len(word) >= 2 and len(keyword) >= 2:
                # Keyword contains word or word contains keyword
                if keyword in word or word in keyword:
                    return True
                    
                # Use fuzzy matching for close matches
                if len(word) >= 3 and len(keyword) >= 3:
                    similarity = fuzz.ratio(keyword, word) / 100.0
                    if similarity >= 0.8:
                        return True
        
        return False
    
    def _calculate_ngram_similarity(self, text1: str, text2: str, n: int = 2) -> float:
        """Calculate n-gram similarity between two texts"""
        def get_ngrams(text: str, n: int) -> set:
            return set(text[i:i+n] for i in range(len(text) - n + 1))
        
        if len(text1) < n or len(text2) < n:
            return 0.0
        
        ngrams1 = get_ngrams(text1, n)
        ngrams2 = get_ngrams(text2, n)
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = ngrams1.intersection(ngrams2)
        union = ngrams1.union(ngrams2)
        
        return len(intersection) / len(union) if union else 0.0
    
    def _calculate_number_match_score(self, keywords: List[str], text: str) -> float:
        """Calculate special score for numbers and government terms"""
        number_keywords = [kw for kw in keywords if re.search(r'\d', kw)]
        if not number_keywords:
            return 0.0

        matches = 0
        for num_kw in number_keywords:
            if num_kw.lower() in text.lower():
                matches += 1

        return matches / len(number_keywords) if number_keywords else 0.0

    def _ensure_document_diversity(self, results: List[Dict], limit: int) -> List[Dict]:
        """Ensure results include diverse documents to capture all mentions"""
        if not results:
            return []

        # Group results by document
        doc_groups = defaultdict(list)
        for result in results:
            doc_id = result.get("doc_id", "unknown")
            doc_groups[doc_id].append(result)

        # Sort each document group by score
        for doc_id in doc_groups:
            doc_groups[doc_id].sort(
                key=lambda x: x.get("rrf_score", 0) + x.get("keyword_relevance", 0),
                reverse=True
            )

        # Build diverse results
        diverse_results = []

        # First pass: Add top result from each document
        for doc_id in sorted(doc_groups.keys()):
            if doc_groups[doc_id]:
                diverse_results.append(doc_groups[doc_id][0])
                if len(diverse_results) >= limit:
                    break

        # Second pass: Add remaining results by score
        if len(diverse_results) < limit:
            remaining = []
            for doc_id in doc_groups:
                # Skip already added results
                remaining.extend(doc_groups[doc_id][1:])

            # Sort remaining by combined score
            remaining.sort(
                key=lambda x: x.get("rrf_score", 0) + x.get("keyword_relevance", 0),
                reverse=True
            )

            # Add best remaining results
            for result in remaining:
                if len(diverse_results) >= limit:
                    break
                diverse_results.append(result)

        logger.info(f"Document diversity: {len(doc_groups)} unique documents in {len(diverse_results)} results")

        return diverse_results