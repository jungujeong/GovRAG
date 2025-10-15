from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional
import asyncio
import logging
from pathlib import Path
import json

from config import config
from eval.golden_evaluator import GoldenEvaluator

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/config")
async def get_configuration() -> Dict:
    """Get current system configuration"""
    return {
        "server": {
            "port": config.APP_PORT,
            "workers": config.WORKERS,
            "timeout": config.REQUEST_TIMEOUT_S
        },
        "indexing": {
            "chunk_tokens": config.CHUNK_TOKENS,
            "chunk_overlap": config.CHUNK_OVERLAP,
            "table_separate": config.TABLE_AS_SEPARATE
        },
        "search": {
            "bm25_weight": config.W_BM25,
            "vector_weight": config.W_VECTOR,
            "rerank_weight": config.W_RERANK,
            "topk_bm25": config.TOPK_BM25,
            "topk_vector": config.TOPK_VECTOR,
            "topk_rerank": config.TOPK_RERANK
        },
        "generation": {
            "model": config.OLLAMA_MODEL,
            "temperature": config.GEN_TEMPERATURE,
            "max_tokens": config.GEN_MAX_TOKENS
        },
        "accuracy": {
            "jaccard_threshold": config.EVIDENCE_JACCARD,
            "citation_similarity": config.CITATION_SENT_SIM,
            "confidence_min": config.CONFIDENCE_MIN
        }
    }

@router.post("/config/update")
async def update_configuration(updates: Dict) -> Dict:
    """Update system configuration (requires restart)"""
    
    # Validate updates
    valid_keys = {
        "CHUNK_TOKENS", "CHUNK_OVERLAP", "W_BM25", "W_VECTOR", 
        "W_RERANK", "TOPK_BM25", "TOPK_VECTOR", "TOPK_RERANK",
        "GEN_TEMPERATURE", "GEN_TOP_P", "GEN_MAX_TOKENS",
        "EVIDENCE_JACCARD", "CITATION_SENT_SIM", "CONFIDENCE_MIN"
    }
    
    for key in updates:
        if key not in valid_keys:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid configuration key: {key}"
            )
    
    # Update config
    for key, value in updates.items():
        setattr(config, key, value)
    
    logger.info(f"Configuration updated: {updates}")
    
    return {
        "status": "updated",
        "updates": updates,
        "message": "Configuration updated. Some changes may require restart."
    }

@router.post("/evaluate")
async def run_evaluation() -> Dict:
    """Run golden QA evaluation"""
    
    golden_file = Path("data/golden/qa_100.json")
    
    if not golden_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Golden QA dataset not found"
        )
    
    try:
        evaluator = GoldenEvaluator()
        results = await evaluator.evaluate_all()
        
        return results
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs")
async def get_recent_logs(lines: int = 100) -> List[str]:
    """Get recent log entries"""
    
    log_file = Path("logs/app.log")
    
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, "r") as f:
            all_lines = f.readlines()
            return all_lines[-lines:]
    except Exception as e:
        logger.error(f"Failed to read logs: {e}")
        return [f"Error reading logs: {e}"]

@router.get("/metrics")
async def get_system_metrics() -> Dict:
    """Get system performance metrics"""
    
    import psutil
    import time
    
    # Get system metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Get process metrics
    process = psutil.Process()
    process_info = {
        "cpu_percent": process.cpu_percent(),
        "memory_mb": process.memory_info().rss / 1024 / 1024,
        "threads": process.num_threads(),
        "open_files": len(process.open_files())
    }
    
    return {
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_gb": memory.available / 1024 / 1024 / 1024,
            "disk_percent": disk.percent,
            "disk_free_gb": disk.free / 1024 / 1024 / 1024
        },
        "process": process_info,
        "timestamp": time.time()
    }

@router.post("/cache/clear")
async def clear_caches() -> Dict:
    """Clear all caches"""
    
    # Clear various caches
    from utils.cache import clear_all_caches
    
    try:
        cleared = clear_all_caches()
        
        return {
            "status": "cleared",
            "caches": cleared
        }
    except Exception as e:
        logger.error(f"Failed to clear caches: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/active")
async def get_active_sessions() -> Dict:
    """Get active session information"""

    # This would typically integrate with session management
    return {
        "active_sessions": 0,
        "total_requests": 0,
        "average_response_time_ms": 0
    }

# ============================================================================
# Enhanced Log Analysis Endpoints
# ============================================================================

@router.get("/logs/statistics")
async def get_log_statistics(date: Optional[str] = None) -> Dict:
    """Get comprehensive log statistics for a specific date"""
    from utils.query_logger import get_query_logger

    try:
        query_logger = get_query_logger()
        stats = query_logger.get_statistics(date)
        return stats
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/search")
async def search_logs(
    query_text: Optional[str] = None,
    date: Optional[str] = None,
    min_confidence: Optional[float] = None,
    has_error: Optional[bool] = None,
    limit: int = 50
) -> List[Dict]:
    """Search logs with various filters"""
    from utils.query_logger import get_query_logger

    try:
        query_logger = get_query_logger()
        logs = query_logger.search_logs(
            query_text=query_text,
            date=date,
            min_confidence=min_confidence,
            has_error=has_error,
            limit=limit
        )
        return logs
    except Exception as e:
        logger.error(f"Failed to search logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/recent")
async def get_recent_queries(limit: int = 20, date: Optional[str] = None) -> List[Dict]:
    """Get recent query logs"""
    from utils.query_logger import get_query_logger

    try:
        query_logger = get_query_logger()
        logs = query_logger.load_logs(date=date, limit=limit)
        return logs
    except Exception as e:
        logger.error(f"Failed to load recent logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/report")
async def generate_log_report(date: Optional[str] = None):
    """Generate HTML report for query logs"""
    from utils.query_logger import get_query_logger

    try:
        query_logger = get_query_logger()
        report_path = query_logger.generate_report(date)

        # Read and return HTML
        with open(report_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content)
    except Exception as e:
        logger.error(f"Failed to generate report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/quality-issues")
async def get_quality_issues(date: Optional[str] = None, limit: int = 20) -> Dict:
    """Get queries with quality issues"""
    from utils.query_logger import get_query_logger

    try:
        query_logger = get_query_logger()
        logs = query_logger.load_logs(date=date)

        # Filter for quality issues
        low_confidence = []
        hallucinations = []
        generic_responses = []
        no_sources = []

        for log in logs:
            qual = log.get('quality_metrics', {})

            if qual.get('confidence_score', 0) < 0.3:
                low_confidence.append({
                    'query': log.get('query'),
                    'timestamp': log.get('timestamp'),
                    'confidence': qual.get('confidence_score', 0)
                })

            if qual.get('hallucination_detected'):
                hallucinations.append({
                    'query': log.get('query'),
                    'timestamp': log.get('timestamp'),
                    'response': log.get('model_response', '')[:200]
                })

            if qual.get('generic_response'):
                generic_responses.append({
                    'query': log.get('query'),
                    'timestamp': log.get('timestamp'),
                    'response': log.get('model_response', '')[:200]
                })

            if qual.get('source_count', 0) == 0 and log.get('query_type') == 'normal':
                no_sources.append({
                    'query': log.get('query'),
                    'timestamp': log.get('timestamp')
                })

        return {
            'low_confidence': low_confidence[:limit],
            'hallucinations': hallucinations[:limit],
            'generic_responses': generic_responses[:limit],
            'no_sources': no_sources[:limit],
            'counts': {
                'low_confidence': len(low_confidence),
                'hallucinations': len(hallucinations),
                'generic_responses': len(generic_responses),
                'no_sources': len(no_sources)
            }
        }
    except Exception as e:
        logger.error(f"Failed to get quality issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/performance-issues")
async def get_performance_issues(date: Optional[str] = None, slow_threshold_ms: int = 5000) -> Dict:
    """Get queries with performance issues"""
    from utils.query_logger import get_query_logger

    try:
        query_logger = get_query_logger()
        logs = query_logger.load_logs(date=date)

        slow_queries = []
        high_memory = []
        high_tokens = []

        for log in logs:
            perf = log.get('performance_metrics', {})

            if perf.get('total_time_ms', 0) > slow_threshold_ms:
                slow_queries.append({
                    'query': log.get('query'),
                    'timestamp': log.get('timestamp'),
                    'total_time_ms': perf.get('total_time_ms', 0),
                    'search_time_ms': perf.get('search_time_ms', 0),
                    'generation_time_ms': perf.get('generation_time_ms', 0)
                })

            if perf.get('memory_used_mb', 0) > 500:
                high_memory.append({
                    'query': log.get('query'),
                    'timestamp': log.get('timestamp'),
                    'memory_mb': perf.get('memory_used_mb', 0)
                })

            if perf.get('total_tokens', 0) > 2000:
                high_tokens.append({
                    'query': log.get('query'),
                    'timestamp': log.get('timestamp'),
                    'tokens': perf.get('total_tokens', 0)
                })

        return {
            'slow_queries': sorted(slow_queries, key=lambda x: x['total_time_ms'], reverse=True)[:20],
            'high_memory': sorted(high_memory, key=lambda x: x['memory_mb'], reverse=True)[:20],
            'high_tokens': sorted(high_tokens, key=lambda x: x['tokens'], reverse=True)[:20],
            'counts': {
                'slow_queries': len(slow_queries),
                'high_memory': len(high_memory),
                'high_tokens': len(high_tokens)
            }
        }
    except Exception as e:
        logger.error(f"Failed to get performance issues: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs/trends")
async def get_log_trends(days: int = 7) -> Dict:
    """Get multi-day trends"""
    from utils.query_logger import get_query_logger
    from datetime import datetime, timedelta

    try:
        query_logger = get_query_logger()
        trends = []

        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            stats = query_logger.get_statistics(date)

            if 'error' not in stats:
                trends.append({
                    'date': date,
                    'total_queries': stats.get('total_queries', 0),
                    'avg_confidence': stats.get('quality', {}).get('avg_confidence', 0),
                    'avg_response_time_ms': stats.get('performance', {}).get('avg_total_time_ms', 0),
                    'error_rate': stats.get('errors', {}).get('error_rate', 0),
                    'hallucination_rate': stats.get('quality', {}).get('hallucination_rate', 0)
                })

        return {
            'trends': list(reversed(trends)),
            'period_days': days
        }
    except Exception as e:
        logger.error(f"Failed to get trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))