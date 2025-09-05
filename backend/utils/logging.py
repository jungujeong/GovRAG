import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Setup application logging"""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Create logger
    logger = logging.getLogger("rag_chatbot")
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    logger.handlers = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_format)
    logger.addHandler(error_handler)
    
    # Set logging for other modules
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("whoosh").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    
    logger.info(f"Logging initialized - Level: {log_level}")
    
    return logger

class AuditLogger:
    """Audit logger for security and compliance"""
    
    def __init__(self):
        # Create audit logger
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)
        
        # Audit file handler
        audit_dir = Path("logs/audit")
        audit_dir.mkdir(parents=True, exist_ok=True)
        
        audit_handler = RotatingFileHandler(
            audit_dir / f"audit_{datetime.now().strftime('%Y%m')}.log",
            maxBytes=50 * 1024 * 1024,  # 50MB
            backupCount=12,  # Keep 1 year
            encoding='utf-8'
        )
        
        audit_format = logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        audit_handler.setFormatter(audit_format)
        self.logger.addHandler(audit_handler)
    
    def log_query(self, user_id: str, query: str, doc_count: int):
        """Log query action"""
        self.logger.info(f"QUERY|{user_id}|{query[:100]}|docs:{doc_count}")
    
    def log_upload(self, user_id: str, filename: str, size: int):
        """Log document upload"""
        self.logger.info(f"UPLOAD|{user_id}|{filename}|size:{size}")
    
    def log_access(self, user_id: str, doc_id: str, action: str):
        """Log document access"""
        self.logger.info(f"ACCESS|{user_id}|{doc_id}|{action}")
    
    def log_error(self, user_id: str, error: str, context: str):
        """Log error event"""
        self.logger.error(f"ERROR|{user_id}|{error}|{context}")

# Global audit logger instance
audit_logger = AuditLogger()