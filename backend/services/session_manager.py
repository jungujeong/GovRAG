import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from uuid import uuid4
import logging
from contextlib import asynccontextmanager
import aiofiles
import aiofiles.os

from models.session import ChatSession, Message, SessionList
from config import config

logger = logging.getLogger(__name__)


class SessionManager:
    """세션 관리 서비스"""
    
    def __init__(self):
        self.sessions_dir = Path(config.DATA_DIR) / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.active_sessions: Dict[str, ChatSession] = {}
        self._lock = asyncio.Lock()
        self._save_queue = asyncio.Queue()
        self._save_task = None
        
    async def initialize(self):
        """초기화 및 백그라운드 저장 태스크 시작"""
        # 기존 세션 로드
        await self._load_sessions()
        # 백그라운드 저장 태스크 시작
        self._save_task = asyncio.create_task(self._background_save())
        logger.info(f"SessionManager initialized with {len(self.active_sessions)} sessions")
    
    async def shutdown(self):
        """종료 및 정리"""
        if self._save_task:
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass
        
        # 모든 세션 저장
        await self._save_all_sessions()
    
    async def _background_save(self):
        """백그라운드 세션 저장 태스크"""
        while True:
            try:
                session_id = await self._save_queue.get()
                if session_id in self.active_sessions:
                    await self._save_session(session_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Background save error: {e}")
    
    async def _load_sessions(self):
        """저장된 세션들 로드"""
        try:
            session_files = list(self.sessions_dir.glob("*.json"))
            for file_path in session_files:
                try:
                    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                        data = json.loads(await f.read())
                        session = self._dict_to_session(data)
                        self.active_sessions[session.id] = session
                except Exception as e:
                    logger.error(f"Failed to load session {file_path}: {e}")
        except Exception as e:
            logger.error(f"Failed to load sessions: {e}")
    
    async def _save_session(self, session_id: str):
        """세션을 파일로 저장"""
        if session_id not in self.active_sessions:
            return
            
        session = self.active_sessions[session_id]
        file_path = self.sessions_dir / f"{session_id}.json"
        
        try:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(session.to_dict(), ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")
    
    async def _save_all_sessions(self):
        """모든 활성 세션 저장"""
        for session_id in self.active_sessions:
            await self._save_session(session_id)
    
    def _dict_to_session(self, data: Dict) -> ChatSession:
        """딕셔너리를 세션 객체로 변환"""
        session = ChatSession(
            id=data["id"],
            title=data["title"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            document_ids=data.get("document_ids", []),
            conversation_summary=data.get("conversation_summary"),
            recent_entities=data.get("recent_entities", []),
            recent_source_doc_ids=data.get("recent_source_doc_ids", []),
            memory_facts=data.get("memory_facts", []),
            is_active=data.get("is_active", True),
            metadata=data.get("metadata"),
            first_response_evidences=data.get("first_response_evidences"),
            first_response_citation_map=data.get("first_response_citation_map")
        )
        
        for msg_data in data.get("messages", []):
            message = Message(
                id=msg_data["id"],
                role=msg_data["role"],
                content=msg_data["content"],
                timestamp=datetime.fromisoformat(msg_data["timestamp"]),
                sources=msg_data.get("sources"),
                metadata=msg_data.get("metadata"),
                error=msg_data.get("error")
            )
            session.messages.append(message)
        
        return session
    
    async def create_session(
        self, 
        title: Optional[str] = None,
        document_ids: Optional[List[str]] = None
    ) -> ChatSession:
        """새 세션 생성"""
        async with self._lock:
            session = ChatSession(
                title=title or "새 대화",
                document_ids=document_ids or []
            )
            self.active_sessions[session.id] = session
            if document_ids is None:
                session.document_ids = []

            if title:
                session.title = title
            # 저장 큐에 추가
            await self._save_queue.put(session.id)
            
            logger.info(f"Created new session: {session.id}")
            return session
    
    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """세션 조회"""
        return self.active_sessions.get(session_id)
    
    async def update_session(
        self,
        session_id: str,
        title: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        conversation_summary: Optional[str] = None,
        recent_entities: Optional[List[str]] = None,
        recent_source_doc_ids: Optional[List[str]] = None,
        first_response_evidences: Optional[List[Dict[str, Any]]] = None,
        first_response_citation_map: Optional[Dict[str, int]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ChatSession]:
        """세션 업데이트"""
        async with self._lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return None
            
            if title is not None:
                session.title = title
            if document_ids is not None:
                session.document_ids = document_ids
            if conversation_summary is not None:
                session.conversation_summary = conversation_summary
            if recent_entities is not None:
                session.recent_entities = recent_entities
            if recent_source_doc_ids is not None:
                session.recent_source_doc_ids = recent_source_doc_ids
            if first_response_evidences is not None:
                session.first_response_evidences = first_response_evidences
            if first_response_citation_map is not None:
                session.first_response_citation_map = first_response_citation_map
            if metadata is not None:
                session.metadata = metadata

            session.updated_at = datetime.now()
            
            # 저장 큐에 추가
            await self._save_queue.put(session_id)
            
            return session
    
    async def delete_session(self, session_id: str) -> bool:
        """세션 삭제"""
        async with self._lock:
            if session_id not in self.active_sessions:
                return False
            
            # 메모리에서 제거
            del self.active_sessions[session_id]
            
            # 파일 삭제
            file_path = self.sessions_dir / f"{session_id}.json"
            try:
                if file_path.exists():
                    await aiofiles.os.remove(file_path)
            except Exception as e:
                logger.error(f"Failed to delete session file {session_id}: {e}")
            
            logger.info(f"Deleted session: {session_id}")
            return True
    
    async def list_sessions(
        self,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = True
    ) -> SessionList:
        """세션 목록 조회"""
        sessions = list(self.active_sessions.values())
        
        # 필터링
        if active_only:
            sessions = [s for s in sessions if s.is_active]
        
        # 정렬 (최신순)
        sessions.sort(key=lambda x: x.updated_at, reverse=True)
        
        # 페이지네이션
        total = len(sessions)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_sessions = sessions[start_idx:end_idx]
        
        # 간단한 정보만 반환
        session_list = [
            {
                "id": s.id,
                "title": s.title,
                "created_at": s.created_at.isoformat(),
                "updated_at": s.updated_at.isoformat(),
                "message_count": len(s.messages),
                "document_count": len(s.document_ids),
                "is_active": s.is_active
            }
            for s in page_sessions
        ]
        
        return SessionList(
            sessions=session_list,
            total=total,
            page=page,
            page_size=page_size
        )
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources: Optional[List] = None,
        error: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Message]:
        """세션에 메시지 추가"""
        async with self._lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return None
            
            message = session.add_message(role, content, sources, error, metadata)

            if role == "user" and not session.conversation_summary:
                session.conversation_summary = content
            
            # 저장 큐에 추가
            await self._save_queue.put(session_id)
            
            return message

    async def add_memory_facts(
        self,
        session_id: str,
        facts: List[Dict[str, str]]
    ) -> bool:
        """세션에 메모리 팩트 추가"""
        if not facts:
            return False

        async with self._lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return False

            session.add_memory_facts(facts)
            await self._save_queue.put(session_id)
            return True
    
    async def get_session_context(
        self,
        session_id: str,
        max_messages: int = 10
    ) -> List[Dict]:
        """세션의 대화 컨텍스트 가져오기"""
        session = self.active_sessions.get(session_id)
        if not session:
            return []
        
        return session.get_context(max_messages)
    
    async def clear_session_messages(self, session_id: str) -> bool:
        """세션 메시지 초기화"""
        async with self._lock:
            session = self.active_sessions.get(session_id)
            if not session:
                return False
            
            session.clear_messages()
            
            # 저장 큐에 추가
            await self._save_queue.put(session_id)
            
            return True
    
    async def cleanup_old_sessions(self, days: int = 30):
        """오래된 세션 정리"""
        cutoff_date = datetime.now() - timedelta(days=days)
        sessions_to_delete = []
        
        for session_id, session in self.active_sessions.items():
            if session.updated_at < cutoff_date:
                sessions_to_delete.append(session_id)
        
        for session_id in sessions_to_delete:
            await self.delete_session(session_id)
        
        logger.info(f"Cleaned up {len(sessions_to_delete)} old sessions")
    
    async def export_session(self, session_id: str) -> Optional[Dict]:
        """세션 내보내기 (백업용)"""
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        return session.to_dict()
    
    async def import_session(self, session_data: Dict) -> Optional[ChatSession]:
        """세션 가져오기 (복원용)"""
        try:
            session = self._dict_to_session(session_data)
            async with self._lock:
                self.active_sessions[session.id] = session
                await self._save_queue.put(session.id)
            return session
        except Exception as e:
            logger.error(f"Failed to import session: {e}")
            return None


# 싱글톤 인스턴스
session_manager = SessionManager()
