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