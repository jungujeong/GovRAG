import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Server/Concurrency
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    WORKERS: int = int(os.getenv("WORKERS", "4"))
    REQUEST_TIMEOUT_S: int = int(os.getenv("REQUEST_TIMEOUT_S", "15"))
    MAX_QUEUE: int = int(os.getenv("MAX_QUEUE", "256"))
    
    # Document/Index
    BASE_DIR = Path(__file__).parent.parent  # Get project root
    DOC_DIR: Path = Path(os.getenv("DOC_DIR", str(BASE_DIR / "data" / "documents")))
    WHOOSH_DIR: Path = Path(os.getenv("WHOOSH_DIR", str(BASE_DIR / "data" / "index")))
    CHROMA_DIR: Path = Path(os.getenv("CHROMA_DIR", str(BASE_DIR / "data" / "chroma")))
    CHUNK_TOKENS: int = int(os.getenv("CHUNK_TOKENS", "2048"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "256"))
    TABLE_AS_SEPARATE: bool = os.getenv("TABLE_AS_SEPARATE", "true").lower() == "true"
    FOOTNOTE_BACKLINK: bool = os.getenv("FOOTNOTE_BACKLINK", "true").lower() == "true"
    
    # Embedding
    PRIMARY_EMBED: str = os.getenv("PRIMARY_EMBED", "BAAI/bge-m3")
    SECONDARY_EMBED: str = os.getenv("SECONDARY_EMBED", "nlpai-lab/KoE5")
    FALLBACK_EMBED: str = os.getenv("FALLBACK_EMBED", "snunlp/KR-SBERT-Medium-extended")
    EMBED_BATCH: int = int(os.getenv("EMBED_BATCH", "16"))
    
    # Hybrid Search Weights
    W_BM25: float = float(os.getenv("W_BM25", "0.4"))
    W_VECTOR: float = float(os.getenv("W_VECTOR", "0.4"))
    W_RERANK: float = float(os.getenv("W_RERANK", "0.2"))
    RRF_K: int = int(os.getenv("RRF_K", "60"))
    TOPK_BM25: int = int(os.getenv("TOPK_BM25", "30"))
    TOPK_VECTOR: int = int(os.getenv("TOPK_VECTOR", "30"))
    TOPK_RERANK: int = int(os.getenv("TOPK_RERANK", "10"))
    
    # Reranker
    RERANKER_ID: str = os.getenv("RERANKER_ID", "jinaai/jina-reranker-v2-base-multilingual")
    RERANK_USE_ONNX: bool = os.getenv("RERANK_USE_ONNX", "true").lower() == "true"
    
    # Generation (LLM)
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3:4b")
    GEN_TEMPERATURE: float = float(os.getenv("GEN_TEMPERATURE", "0.0"))
    GEN_TOP_P: float = float(os.getenv("GEN_TOP_P", "1.0"))
    GEN_MAX_TOKENS: int = int(os.getenv("GEN_MAX_TOKENS", "1024"))
    
    # Accuracy Thresholds
    EVIDENCE_JACCARD: float = float(os.getenv("EVIDENCE_JACCARD", "0.55"))
    CITATION_SENT_SIM: float = float(os.getenv("CITATION_SENT_SIM", "0.9"))
    CITATION_SPAN_IOU: float = float(os.getenv("CITATION_SPAN_IOU", "0.5"))
    CONFIDENCE_MIN: float = float(os.getenv("CONFIDENCE_MIN", "0.7"))
    
    # Security/Session
    SESSION_TIMEOUT_S: int = int(os.getenv("SESSION_TIMEOUT_S", "3600"))
    AUDIT_LOG_RETENTION_D: int = int(os.getenv("AUDIT_LOG_RETENTION_D", "90"))
    PII_MASKING: bool = os.getenv("PII_MASKING", "true").lower() == "true"
    
    @classmethod
    def validate(cls):
        """Validate configuration"""
        cls.DOC_DIR.mkdir(parents=True, exist_ok=True)
        cls.WHOOSH_DIR.mkdir(parents=True, exist_ok=True)
        cls.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        
        if cls.W_BM25 + cls.W_VECTOR + cls.W_RERANK > 1.01:
            raise ValueError("Search weights must sum to <= 1.0")
        
        return True

config = Config()