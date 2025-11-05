from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import uuid4


class Message(BaseModel):
    """채팅 메시지 모델"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    sources: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ChatSession(BaseModel):
    """채팅 세션 모델"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = "새 대화"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    messages: List[Message] = Field(default_factory=list)
    document_ids: List[str] = Field(default_factory=list)  # 이 세션에서 참조하는 문서 ID들
    recent_source_doc_ids: List[str] = Field(default_factory=list)
    conversation_summary: Optional[str] = None
    recent_entities: List[str] = Field(default_factory=list)
    memory_facts: List[Dict[str, str]] = Field(default_factory=list)
    is_active: bool = True
    metadata: Optional[Dict[str, Any]] = None
    # 첫 답변에서 사용한 evidence들을 고정하여 저장
    first_response_evidences: Optional[List[Dict[str, Any]]] = None
    # 첫 답변의 citation 번호 매핑 저장 (evidence_key -> citation_number)
    first_response_citation_map: Optional[Dict[str, int]] = None
    
    def add_message(self, role: str, content: str, sources: Optional[List] = None, error: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        """메시지 추가"""
        message = Message(
            role=role,
            content=content,
            sources=sources,
            metadata=metadata,
            error=error
        )
        self.messages.append(message)
        self.updated_at = datetime.now()

        # 첫 사용자 메시지로 제목 및 기본 요약 설정
        if len(self.messages) == 1 and role == "user":
            self.title = content[:30] + ("..." if len(content) > 30 else "")
            if not self.conversation_summary:
                self.conversation_summary = content
        
        return message

    def add_memory_facts(self, facts: List[Dict[str, str]]):
        """Store memory facts ensuring uniqueness and bounded size"""
        if not facts:
            return

        existing = {(fact.get("doc_id"), fact.get("text")) for fact in self.memory_facts}

        for fact in facts:
            doc_id = fact.get("doc_id")
            text = fact.get("text")
            if not doc_id or not text:
                continue
            key = (doc_id, text)
            if key in existing:
                continue
            self.memory_facts.append({"doc_id": doc_id, "text": text})
            existing.add(key)

        if len(self.memory_facts) > 50:
            self.memory_facts = self.memory_facts[-50:]
    
    def get_context(self, max_messages: int = 10) -> List[Dict]:
        """대화 컨텍스트 가져오기"""
        recent_messages = self.messages[-max_messages:] if max_messages else self.messages
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in recent_messages
        ]
    
    def clear_messages(self):
        """메시지 초기화"""
        self.messages = []
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    "sources": msg.sources,
                    "metadata": msg.metadata,
                    "error": msg.error
                }
                for msg in self.messages
            ],
            "document_ids": self.document_ids,
            "conversation_summary": self.conversation_summary,
            "recent_entities": self.recent_entities,
            "recent_source_doc_ids": self.recent_source_doc_ids,
            "memory_facts": self.memory_facts,
            "is_active": self.is_active,
            "metadata": self.metadata
        }


class SessionList(BaseModel):
    """세션 목록 응답 모델"""
    sessions: List[Dict[str, Any]]
    total: int
    page: int = 1
    page_size: int = 20
