from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from config import config
from routers import query, admin, documents
from utils.log_utils import setup_logging

# Setup logging
logger = setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("Starting RAG Chatbot System...")
    config.validate()
    
    # Initialize indexes if they don't exist
    from rag.whoosh_bm25 import WhooshBM25
    from rag.chroma_store import ChromaStore
    
    WhooshBM25.initialize()
    ChromaStore.initialize()
    
    logger.info("System ready!")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="RAG Chatbot System",
    description="Evidence-Only RAG for Korean Government Documents",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(query.router, prefix="/api/query", tags=["Query"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

@app.get("/")
async def root():
    return {
        "service": "RAG Chatbot System",
        "version": "1.0.0",
        "status": "online"
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Ollama
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{config.OLLAMA_HOST}/api/tags", timeout=2.0)
                ollama_status = response.status_code == 200
            except:
                ollama_status = False
        
        # Check indexes
        whoosh_exists = Path(config.WHOOSH_DIR).exists()
        chroma_exists = Path(config.CHROMA_DIR).exists()
        
        return {
            "status": "healthy" if ollama_status else "degraded",
            "components": {
                "ollama": ollama_status,
                "whoosh": whoosh_exists,
                "chroma": chroma_exists
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e)}
        )

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )