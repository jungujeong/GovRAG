from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class QueryRequest(BaseModel):
    """Query request schema"""
    query: str = Field(..., min_length=1, max_length=1000, description="User query")
    doc_ids: Optional[List[str]] = Field(None, description="Filter by document IDs")
    doc_types: Optional[List[str]] = Field(None, description="Filter by document types")
    limit: int = Field(10, ge=1, le=50, description="Maximum results to return")
    stream: bool = Field(False, description="Enable streaming response")

class Citation(BaseModel):
    """Citation information"""
    doc_id: str
    page: int
    start_char: int
    end_char: int
    chunk_id: Optional[str] = None
    text_snippet: Optional[str] = None

class QueryResponse(BaseModel):
    """Query response schema"""
    query: str
    answer: str
    key_facts: List[str]
    details: Optional[str] = ""
    sources: List[Citation]
    formatted_text: Optional[str] = None
    formatted_html: Optional[str] = None
    formatted_markdown: Optional[str] = None
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class DocumentUploadResponse(BaseModel):
    """Document upload response"""
    status: str
    filename: str
    path: str
    message: str
    chunks: Optional[int] = None

class DocumentInfo(BaseModel):
    """Document information"""
    filename: str
    path: str
    size: int
    modified: float
    type: str

class IndexStats(BaseModel):
    """Index statistics"""
    total_documents: int
    total_chunks: int
    index_size_mb: float
    last_updated: Optional[datetime] = None

class EvaluationResult(BaseModel):
    """Evaluation result schema"""
    question_id: str
    question: str
    expected_answer: str
    generated_answer: str
    exact_match: float
    f1_score: float
    citation_accuracy: float
    hallucination_detected: bool

class EvaluationSummary(BaseModel):
    """Evaluation summary"""
    total_questions: int
    average_exact_match: float
    average_f1: float
    average_citation_accuracy: float
    hallucination_rate: float
    passed: bool
    details: List[EvaluationResult]

class ConfigUpdate(BaseModel):
    """Configuration update request"""
    key: str
    value: Any
    
class SystemHealth(BaseModel):
    """System health status"""
    status: str = Field(..., pattern="^(healthy|degraded|unhealthy)$")
    components: Dict[str, bool]
    timestamp: datetime = Field(default_factory=datetime.now)

class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)