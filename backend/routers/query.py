from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional
import asyncio
import logging
import time
from datetime import datetime
import uuid

from schemas import QueryRequest, QueryResponse
from rag.hybrid_retriever import HybridRetriever
from rag.reranker import Reranker
from rag.generator_ollama import OllamaGenerator
from rag.evidence_enforcer import EvidenceEnforcer
from rag.citation_tracker import CitationTracker
from rag.answer_formatter import AnswerFormatter
from config import config
from utils.query_logger import (
    get_query_logger,
    QueryLog,
    SearchResult,
    QualityMetrics,
    PerformanceMetrics,
    RetrievalMetrics,
    ErrorInfo
)

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
    """Process a RAG query with comprehensive logging"""
    start_time = time.time()
    session_id = str(uuid.uuid4())
    query_logger = get_query_logger()

    # Initialize timing markers
    search_start = 0
    search_end = 0
    rerank_start = 0
    rerank_end = 0
    generation_start = 0
    generation_end = 0

    # Initialize log data
    query_type = "normal"
    evidences = []
    response = {}
    error_info = ErrorInfo()

    try:
        logger.info(f"Processing query [{session_id}]: {request.query[:100]}...")

        # Check for greeting or general queries
        greetings = ["안녕", "hello", "hi", "도움", "help", "뭐해", "뭐하니", "안녕하세요"]
        is_greeting = any(greeting in request.query.lower() for greeting in greetings)

        if is_greeting:
            query_type = "greeting"
            answer = "안녕하세요! 문서에 대해 궁금한 점이 있으시면 질문해 주세요."

            # Log greeting query
            query_log = QueryLog(
                timestamp=datetime.now().isoformat(),
                session_id=session_id,
                query=request.query,
                query_type=query_type,
                model_name=config.OLLAMA_MODEL,
                model_response=answer,
                performance_metrics=PerformanceMetrics(
                    total_time_ms=(time.time() - start_time) * 1000
                )
            )
            query_logger.log_query(query_log)

            return QueryResponse(
                query=request.query,
                answer=answer,
                key_facts=[],
                sources=[],
                metadata={"type": "greeting", "session_id": session_id}
            )

        # 1. Retrieve relevant documents
        search_start = time.time()
        retriever = get_retriever()
        evidences = retriever.retrieve(
            request.query,
            limit=config.TOPK_BM25 + config.TOPK_VECTOR
        )
        search_end = time.time()

        if not evidences:
            query_type = "no_evidence"
            logger.warning("No evidences found")
            answer = "죄송합니다. 질문과 관련된 문서를 찾을 수 없습니다. 다른 질문을 해주시거나 문서를 먼저 업로드해 주세요."

            # Log no evidence query
            query_log = QueryLog(
                timestamp=datetime.now().isoformat(),
                session_id=session_id,
                query=request.query,
                query_type=query_type,
                model_name=config.OLLAMA_MODEL,
                model_response=answer,
                performance_metrics=PerformanceMetrics(
                    search_time_ms=(search_end - search_start) * 1000,
                    total_time_ms=(time.time() - start_time) * 1000
                )
            )
            query_logger.log_query(query_log)

            return QueryResponse(
                query=request.query,
                answer=answer,
                key_facts=[],
                sources=[],
                error="no_evidence",
                metadata={"session_id": session_id}
            )

        # 2. Rerank if available
        rerank_start = time.time()
        reranker = get_reranker()
        if reranker.model or (reranker.use_onnx and hasattr(reranker, 'ort_session')):
            evidences = reranker.rerank(
                request.query,
                evidences,
                top_k=config.TOPK_RERANK
            )
        else:
            evidences = evidences[:config.TOPK_RERANK]
        rerank_end = time.time()

        # 3. Generate response
        generation_start = time.time()
        generator = get_generator()
        response = await generator.generate(
            request.query,
            evidences,
            stream=request.stream
        )
        generation_end = time.time()

        # 4. Verify and enforce evidence
        enforcer = get_enforcer()
        response = enforcer.enforce_evidence(response, evidences)

        # 5. Track citations
        citation_tracker = get_citation_tracker()
        response = citation_tracker.track_citations(response, evidences)

        # 6. Format response
        formatter = get_formatter()
        response = formatter.format_response(response)

        # 7. Check if response is generic or lacks evidence
        answer_text = response.get("answer", "").lower()
        generic_phrases = [
            "죄송합니다", "찾을 수 없습니다", "모르겠습니다",
            "정보가 없습니다", "알 수 없습니다", "근거가 부족합니다",
            "문서에 없습니다", "확인할 수 없습니다", "판단하기 어렵습니다"
        ]

        is_generic = any(phrase in answer_text for phrase in generic_phrases)
        has_low_confidence = response.get("verification", {}).get("confidence", 0) < 0.3
        has_hallucination = response.get("verification", {}).get("hallucination_detected", False)

        # Remove sources if response is generic or unreliable
        if is_generic or has_low_confidence or has_hallucination:
            response["sources"] = []
            logger.info("Removed sources due to generic/unreliable response")

        # 8. Calculate metrics and log
        end_time = time.time()

        # Performance metrics
        perf_metrics = PerformanceMetrics(
            search_time_ms=(search_end - search_start) * 1000,
            rerank_time_ms=(rerank_end - rerank_start) * 1000,
            generation_time_ms=(generation_end - generation_start) * 1000,
            total_time_ms=(end_time - start_time) * 1000
        )

        # Capture system performance
        perf_metrics = query_logger.capture_performance_metrics()
        perf_metrics.search_time_ms = (search_end - search_start) * 1000
        perf_metrics.rerank_time_ms = (rerank_end - rerank_start) * 1000
        perf_metrics.generation_time_ms = (generation_end - generation_start) * 1000
        perf_metrics.total_time_ms = (end_time - start_time) * 1000

        # Quality metrics
        quality_metrics = query_logger.calculate_quality_metrics(
            response,
            evidences,
            response.get("answer", "")
        )

        # Retrieval metrics
        retrieval_metrics = RetrievalMetrics(
            final_count=len(evidences)
        )

        # Convert evidences to SearchResult format
        search_results = []
        for ev in evidences[:10]:  # Log top 10 only
            search_results.append(SearchResult(
                chunk_id=ev.get('chunk_id', ''),
                doc_id=ev.get('doc_id', ''),
                page=ev.get('page', 0),
                text_preview=ev.get('text', '')[:200],
                rrf_score=ev.get('rrf_score', 0.0),
                keyword_relevance=ev.get('keyword_relevance', 0.0),
                bm25_score=ev.get('bm25_score', 0.0),
                vector_score=ev.get('vector_score', 0.0),
                include_reason=ev.get('include_reason', 'unknown')
            ))

        # Create and log query
        query_log = QueryLog(
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            query=request.query,
            query_type=query_type,
            extracted_keywords=request.query.split()[:10],  # Simple tokenization
            retrieval_metrics=retrieval_metrics,
            search_results=search_results,
            model_name=config.OLLAMA_MODEL,
            model_response=response.get("answer", ""),
            response_sources=response.get("sources", []),
            quality_metrics=quality_metrics,
            performance_metrics=perf_metrics,
            error_info=error_info
        )

        query_logger.log_query(query_log)

        # 9. Create final response
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
                "processing_time": perf_metrics.total_time_ms,
                "session_id": session_id
            }
        )

    except Exception as e:
        logger.error(f"Query processing failed: {e}")

        # Log error
        error_info = ErrorInfo(
            has_error=True,
            error_type=type(e).__name__,
            error_message=str(e),
            error_traceback=""
        )

        query_log = QueryLog(
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            query=request.query,
            query_type="error",
            model_name=config.OLLAMA_MODEL,
            error_info=error_info,
            performance_metrics=PerformanceMetrics(
                total_time_ms=(time.time() - start_time) * 1000
            )
        )
        query_logger.log_query(query_log)

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