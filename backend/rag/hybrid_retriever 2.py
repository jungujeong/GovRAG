from typing import List, Dict, Optional, Tuple
import numpy as np
from collections import defaultdict
import logging
import re
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
    
    def retrieve(self, query: str, limit: int = 10) -> List[Dict]:
        """Retrieve documents using hybrid search"""
        # Normalize query
        normalized_query = self.normalizer.normalize_query(query)
        
        # BM25 search
        bm25_results = self._bm25_search(normalized_query)
        
        # Vector search
        vector_results = self._vector_search(query)  # Use original query for embedding
        
        # Combine with RRF
        combined_results = self._reciprocal_rank_fusion(
            bm25_results,
            vector_results
        )
        
        # Filter by relevance
        filtered_results = self._filter_by_relevance(query, combined_results)
        
        # Return top results
        return filtered_results[:limit]
    
    def _bm25_search(self, query: str) -> List[Dict]:
        """Perform BM25 search"""
        try:
            results = self.bm25.search(query, limit=config.TOPK_BM25)
            
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
    
    def _vector_search(self, query: str) -> List[Dict]:
        """Perform vector similarity search"""
        try:
            # Generate query embedding
            query_embedding = self.embedder.encode_query(query)
            
            # Search in ChromaDB
            results = self.chroma.search(
                query_embedding.tolist(),
                limit=config.TOPK_VECTOR
            )
            
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
                           min_score: float = 0.05, 
                           keyword_threshold: float = 0.15) -> List[Dict]:
        """Filter results by relevance using multiple criteria with fallback"""
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
            
            # More permissive filtering criteria
            include_reason = None
            if keyword_relevance >= keyword_threshold:
                include_reason = f"keyword_rel={keyword_relevance:.3f} >= {keyword_threshold}"
            elif rrf_score >= 0.5:  # Lowered from 0.7
                include_reason = f"high_semantic={rrf_score:.3f} >= 0.5"
            elif rrf_score >= min_score and keyword_relevance >= 0.1:  # More lenient fallback
                include_reason = f"moderate_match rrf={rrf_score:.3f}, kw={keyword_relevance:.3f}"
            
            if include_reason:
                filtered_results.append(result)
                debug_info.append(f"Result {i}: INCLUDED - {include_reason}")
            else:
                debug_info.append(f"Result {i}: FILTERED - rrf={rrf_score:.3f}, kw={keyword_relevance:.3f}")
        
        # If still no results, apply emergency fallback
        if not filtered_results and len(results) > 0:
            logger.warning("No results passed filtering, applying emergency fallback")
            # Take top 3 results by RRF score regardless of keywords
            emergency_results = sorted(results, key=lambda x: x.get("rrf_score", 0), reverse=True)[:3]
            for result in emergency_results:
                if "keyword_relevance" not in result:
                    result["keyword_relevance"] = self._calculate_keyword_relevance(query_keywords, result.get("text", ""))
            filtered_results = emergency_results
            logger.info(f"Emergency fallback: included {len(filtered_results)} top results")
        
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
        """Extract meaningful keywords from query using pattern-based approach"""
        keywords = []
        
        # 1. Extract important patterns first
        
        # Numbers and dates (always important)
        numbers = re.findall(r'\d+(?:년|월|일|호|회|차|번|개|명|건)?', query)
        keywords.extend(numbers)
        
        # Government terms (제X호, X조, X항 등)
        gov_terms = re.findall(r'제\s*\d+\s*[호조항차회]', query)
        keywords.extend(gov_terms)
        
        # 2. Extract content words (명사 중심)
        
        # Find potential nouns: 2+ character Korean words
        korean_words = re.findall(r'[가-힣]{2,}', query)
        
        for word in korean_words:
            # Filter by word characteristics rather than hardcoded lists
            if self._is_content_word(word):
                keywords.append(word)
        
        # 3. Extract proper nouns and technical terms
        # English terms and mixed terms
        english_terms = re.findall(r'[a-zA-Z][a-zA-Z0-9]*', query)
        keywords.extend([term for term in english_terms if len(term) >= 2])
        
        # 4. If very few keywords extracted, add single-character Korean words as fallback
        if len(keywords) < 2:
            single_chars = re.findall(r'[가-힣]', query)
            keywords.extend([char for char in single_chars if char not in ['은', '는', '이', '가', '을', '를', '에', '의', '도', '만', '와', '과', '로', '서', '부터', '까지']])
        
        # Remove duplicates and return
        unique_keywords = list(set(keywords))
        logger.debug(f"Keyword extraction: '{query}' -> {unique_keywords}")
        return unique_keywords
    
    def _is_content_word(self, word: str) -> bool:
        """Determine if a Korean word is a content word (명사, 동사 어간 등)"""
        if len(word) < 2:
            return False
        
        # 1. 길이가 길수록 내용어일 가능성 높음
        if len(word) >= 4:
            return True
        
        # 2. 특정 접미사로 끝나는 경우 제외 (조사, 어미)
        functional_endings = ['하다', '되다', '이다', '하는', '되는', '한다', '된다']
        if any(word.endswith(ending) for ending in functional_endings):
            return False
        
        # 3. 단일 음절 조사들 제외
        single_syllable_particles = ['은', '는', '이', '가', '을', '를', '에', '의', '도', '만', '도', '와', '과']
        if word in single_syllable_particles:
            return False
        
        # 4. 빈도 높은 기능어 제외 (최소한만)
        common_function_words = ['그리고', '하지만', '그러나', '또한', '그런데', '따라서', '그래서']
        if word in common_function_words:
            return False
        
        # 5. 정부/공문서 관련 중요 용어는 항상 포함
        important_terms = ['구청', '청장', '지시', '사항', '예산', '편성', '회의', '계획', '사업', '정책']
        if any(term in word for term in important_terms):
            return True
        
        # 6. 기본적으로 2글자 이상이면 내용어로 간주
        return True
    
    def _calculate_keyword_relevance(self, keywords: List[str], text: str) -> float:
        """Calculate keyword relevance score with improved Korean handling"""
        if not keywords:
            return 0.0
        
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
        
        # 5. Combined score with weights
        total_score = (
            exact_score * 0.5 +           # Exact matches most important
            partial_score * 0.2 +         # Partial matches
            ngram_score * 0.2 +           # Semantic similarity
            number_match_score * 0.1      # Number/term matching
        )
        
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