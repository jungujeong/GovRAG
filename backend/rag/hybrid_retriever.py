from typing import List, Dict, Optional, Tuple
import numpy as np
from collections import defaultdict
import logging

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
        
        # Return top results
        return combined_results[:limit]
    
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