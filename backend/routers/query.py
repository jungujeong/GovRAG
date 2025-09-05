from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional
import asyncio
import logging

from schemas import QueryRequest, QueryResponse
from rag.hybrid_retriever import HybridRetriever
from rag.reranker import Reranker
from rag.generator_ollama import OllamaGenerator
from rag.evidence_enforcer import EvidenceEnforcer
from rag.citation_tracker import CitationTracker
from rag.answer_formatter import AnswerFormatter
from config import config

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy initialization of components
_retriever = None
_reranker = None
_generator = None
_enforcer = None
_citation_tracker = None
_formatter = None

def get_retriever():
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever

def get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker

def get_generator():
    global _generator
    if _generator is None:
        _generator = OllamaGenerator()
    return _generator

def get_enforcer():
    global _enforcer
    if _enforcer is None:
        _enforcer = EvidenceEnforcer()
    return _enforcer

def get_citation_tracker():
    global _citation_tracker
    if _citation_tracker is None:
        _citation_tracker = CitationTracker()
    return _citation_tracker

def get_formatter():
    global _formatter
    if _formatter is None:
        _formatter = AnswerFormatter()
    return _formatter

@router.get("/test")
async def test_retrieval(q: str = "테스트"):
    """Simple test endpoint for retrieval"""
    try:
        from rag.whoosh_bm25 import WhooshBM25
        from rag.chroma_store import ChromaStore
        
        # Test Whoosh search
        whoosh = WhooshBM25()
        whoosh_results = whoosh.search(q, limit=5)
        
        # Test Chroma search  
        chroma = ChromaStore()
        # For now, skip embedding to avoid blocking
        
        return {
            "query": q,
            "whoosh_results": len(whoosh_results),
            "whoosh_sample": whoosh_results[0] if whoosh_results else None
        }
    except Exception as e:
        import traceback
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@router.post("/", response_model=QueryResponse)
async def process_query(request: QueryRequest) -> QueryResponse:
    """Process a RAG query"""
    try:
        logger.info(f"Processing query: {request.query[:100]}...")
        
        # 1. Retrieve relevant documents
        retriever = get_retriever()
        evidences = retriever.retrieve(
            request.query,
            limit=config.TOPK_BM25 + config.TOPK_VECTOR
        )
        
        if not evidences:
            logger.warning("No evidences found")
            return QueryResponse(
                query=request.query,
                answer="관련 문서를 찾을 수 없습니다.",
                key_facts=[],
                sources=[],
                error="no_evidence"
            )
        
        # 2. Rerank if available
        reranker = get_reranker()
        if reranker.model or (reranker.use_onnx and hasattr(reranker, 'ort_session')):
            evidences = reranker.rerank(
                request.query,
                evidences,
                top_k=config.TOPK_RERANK
            )
        else:
            # Use top K without reranking
            evidences = evidences[:config.TOPK_RERANK]
        
        # 3. Generate response
        generator = get_generator()
        response = await generator.generate(
            request.query,
            evidences,
            stream=request.stream
        )
        
        # 4. Verify and enforce evidence
        enforcer = get_enforcer()
        response = enforcer.enforce_evidence(response, evidences)
        
        # 5. Track citations
        citation_tracker = get_citation_tracker()
        response = citation_tracker.track_citations(response, evidences)
        
        # 6. Format response
        formatter = get_formatter()
        response = formatter.format_response(response)
        
        # 7. Create final response
        return QueryResponse(
            query=request.query,
            answer=response.get("answer", ""),
            key_facts=response.get("key_facts", []),
            details=response.get("details", ""),
            sources=response.get("sources", []),
            formatted_text=response.get("formatted_text", ""),
            formatted_html=response.get("formatted_html", ""),
            formatted_markdown=response.get("formatted_markdown", ""),
            confidence=response.get("verification", {}).get("confidence", 0),
            metadata={
                "evidence_count": len(evidences),
                "hallucination_detected": response.get("verification", {}).get("hallucination_detected", False),
                "processing_time": 0  # TODO: Add timing
            }
        )
        
    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream")
async def process_query_stream(request: QueryRequest):
    """Process query with streaming response"""
    try:
        # Get evidences
        evidences = retriever.retrieve(request.query)
        
        if not evidences:
            yield {"error": "no_evidence"}
            return
        
        # Rerank if available
        if reranker.model:
            evidences = reranker.rerank(request.query, evidences)
        
        # Stream generation
        async for chunk in generator._generate_stream({
            "model": generator.model,
            "messages": [
                {"role": "system", "content": generator.PromptTemplates.get_system_prompt()},
                {"role": "user", "content": generator.PromptTemplates.format_user_prompt(request.query, evidences)}
            ],
            "temperature": generator.temperature,
            "stream": True
        }):
            yield {"content": chunk}
        
    except Exception as e:
        logger.error(f"Streaming failed: {e}")
        yield {"error": str(e)}

@router.get("/health")
async def health_check():
    """Check query service health"""
    try:
        # Check Ollama
        ollama_healthy = await generator.check_health()
        
        return {
            "status": "healthy" if ollama_healthy else "degraded",
            "ollama": ollama_healthy,
            "retriever": True,
            "reranker": reranker.model is not None
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }