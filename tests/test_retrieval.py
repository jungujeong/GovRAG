import pytest
import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent.parent))

from backend.rag.hybrid_retriever import HybridRetriever
from backend.rag.whoosh_bm25 import WhooshBM25
from backend.rag.chroma_store import ChromaStore
from backend.rag.embedder import Embedder

@pytest.fixture
def retriever():
    """Create retriever instance"""
    return HybridRetriever()

@pytest.fixture
def sample_chunks():
    """Create sample chunks for testing"""
    return [
        {
            "chunk_id": "test-chunk-1",
            "doc_id": "test_doc",
            "text": "2024년도 예산 편성 지침에 따르면 디지털 전환 예산이 10% 증액되었습니다.",
            "page": 1,
            "start_char": 0,
            "end_char": 100,
            "type": "content"
        },
        {
            "chunk_id": "test-chunk-2",
            "doc_id": "test_doc",
            "text": "탄소중립 관련 예산이 신설되어 총 500억원이 배정되었습니다.",
            "page": 2,
            "start_char": 100,
            "end_char": 200,
            "type": "content"
        },
        {
            "chunk_id": "test-chunk-3",
            "doc_id": "test_doc",
            "text": "지방교부세율이 0.5%p 상향 조정되어 지방재정이 강화됩니다.",
            "page": 3,
            "start_char": 200,
            "end_char": 300,
            "type": "content"
        }
    ]

def test_bm25_search(sample_chunks):
    """Test BM25 search functionality"""
    # Initialize and index
    bm25 = WhooshBM25()
    bm25.clear_index()
    bm25.index_chunks(sample_chunks)
    
    # Search
    results = bm25.search("예산 편성", limit=5)
    
    # Verify
    assert len(results) > 0
    assert any("예산" in r["text"] for r in results)

def test_vector_search(sample_chunks):
    """Test vector search functionality"""
    # Initialize
    chroma = ChromaStore()
    embedder = Embedder()
    
    # Clear and index
    chroma.clear_collection()
    
    texts = [chunk["text"] for chunk in sample_chunks]
    embeddings = embedder.embed_batch(texts)
    
    chroma.index_chunks(sample_chunks, embeddings)
    
    # Search
    query_embedding = embedder.encode_query("디지털 전환 예산")
    results = chroma.search(query_embedding.tolist(), limit=5)
    
    # Verify
    assert len(results) > 0
    assert results[0]["chunk_id"] in [c["chunk_id"] for c in sample_chunks]

def test_hybrid_retrieval(retriever, sample_chunks):
    """Test hybrid retrieval"""
    # Index sample data
    retriever.bm25.clear_index()
    retriever.bm25.index_chunks(sample_chunks)
    
    retriever.chroma.clear_collection()
    texts = [chunk["text"] for chunk in sample_chunks]
    embeddings = retriever.embedder.embed_batch(texts)
    retriever.chroma.index_chunks(sample_chunks, embeddings)
    
    # Retrieve
    results = retriever.retrieve("탄소중립 예산", limit=3)
    
    # Verify
    assert len(results) > 0
    assert "rrf_score" in results[0]
    assert "hybrid_score" in results[0]

def test_rrf_fusion():
    """Test Reciprocal Rank Fusion"""
    retriever = HybridRetriever()
    
    # Mock results
    bm25_results = [
        {"chunk_id": "1", "text": "text1", "normalized_score": 1.0},
        {"chunk_id": "2", "text": "text2", "normalized_score": 0.8},
        {"chunk_id": "3", "text": "text3", "normalized_score": 0.6}
    ]
    
    vector_results = [
        {"chunk_id": "2", "text": "text2", "normalized_score": 0.9},
        {"chunk_id": "3", "text": "text3", "normalized_score": 0.7},
        {"chunk_id": "4", "text": "text4", "normalized_score": 0.5}
    ]
    
    # Fuse
    combined = retriever._reciprocal_rank_fusion(bm25_results, vector_results)
    
    # Verify
    assert len(combined) == 4  # 4 unique chunks
    assert combined[0]["chunk_id"] in ["1", "2"]  # Top results
    assert all("rrf_score" in r for r in combined)

def test_retrieval_with_filters(retriever):
    """Test filtered retrieval"""
    # Mock some data
    sample_chunks = [
        {
            "chunk_id": "pdf-1",
            "doc_id": "doc1.pdf",
            "text": "PDF content",
            "type": "content",
            "page": 1,
            "start_char": 0,
            "end_char": 100
        },
        {
            "chunk_id": "hwp-1",
            "doc_id": "doc2.hwp",
            "text": "HWP content",
            "type": "content",
            "page": 1,
            "start_char": 0,
            "end_char": 100
        }
    ]
    
    # Index
    retriever.bm25.clear_index()
    retriever.bm25.index_chunks(sample_chunks)
    
    # Test with filters
    results = retriever.retrieve_with_filters(
        "content",
        doc_ids=["doc1.pdf"],
        limit=5
    )
    
    # All results should be from doc1.pdf
    for result in results:
        if "doc_id" in result:
            assert result["doc_id"] == "doc1.pdf"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])