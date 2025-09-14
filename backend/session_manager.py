"""
Session Management System
세션 상태 보존, 대화 히스토리, carry-over facts 관리
"""

import json
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
import asyncio
import aiofiles
from pydantic import BaseModel, Field
import hashlib
import logging

logger = logging.getLogger(__name__)

class SessionState(BaseModel):
    """세션 상태 모델"""
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    title_auto: Optional[str] = None
    title_user: Optional[str] = None
    messages: List[Dict] = Field(default_factory=list)
    carry_over_facts: Optional[str] = None
    pending_request: Optional[Dict] = None
    scroll_position: int = 0
    is_active: bool = True
    archived: bool = False
    
    @property
    def title(self) -> str:
        """사용자 제목 우선, 없으면 자동 제목"""
        return self.title_user or self.title_auto or "새 대화"
    
    def to_storage(self) -> Dict:
        """저장용 딕셔너리 변환"""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "title_auto": self.title_auto,
            "title_user": self.title_user,
            "messages": self.messages,
            "carry_over_facts": self.carry_over_facts,
            "pending_request": self.pending_request,
            "scroll_position": self.scroll_position,
            "is_active": self.is_active,
            "archived": self.archived
        }
    
    @classmethod
    def from_storage(cls, data: Dict) -> 'SessionState':
        """저장된 데이터에서 복원"""
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)

class DraftState(BaseModel):
    """클라이언트 초안 상태 (2초마다 저장)"""
    session_id: str
    messages: List[Dict]
    pending_request: Optional[Dict] = None
    scroll_position: int = 0
    last_saved: datetime = Field(default_factory=datetime.now)
    partial_tokens: Optional[str] = None

class SessionManager:
    """세션 관리자"""
    
    def __init__(self, storage_dir: str = "./data/sessions"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.active_sessions: Dict[str, SessionState] = {}
        self.draft_cache: Dict[str, DraftState] = {}
        self._save_lock = asyncio.Lock()
        self._auto_save_task = None
    
    async def start(self):
        """자동 저장 태스크 시작"""
        self._auto_save_task = asyncio.create_task(self._auto_save_loop())
        await self._load_recent_sessions()
    
    async def stop(self):
        """자동 저장 태스크 중지"""
        if self._auto_save_task:
            self._auto_save_task.cancel()
            await self._flush_all_drafts()
    
    async def _auto_save_loop(self):
        """2초마다 초안 저장"""
        while True:
            try:
                await asyncio.sleep(2)
                await self._save_drafts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Auto-save error: {e}")
    
    async def _save_drafts(self):
        """초안 상태 저장"""
        async with self._save_lock:
            for session_id, draft in self.draft_cache.items():
                if (datetime.now() - draft.last_saved).seconds >= 2:
                    await self._persist_draft(session_id, draft)
                    draft.last_saved = datetime.now()
    
    async def _persist_draft(self, session_id: str, draft: DraftState):
        """초안을 파일시스템에 저장"""
        draft_path = self.storage_dir / f"draft_{session_id}.json"
        try:
            async with aiofiles.open(draft_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(draft.model_dump(mode='json'), 
                                        ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Failed to persist draft {session_id}: {e}")
    
    async def _flush_all_drafts(self):
        """모든 초안 즉시 저장"""
        for session_id, draft in self.draft_cache.items():
            await self._persist_draft(session_id, draft)
    
    async def _load_recent_sessions(self, limit: int = 50):
        """최근 세션 로드"""
        session_files = sorted(
            self.storage_dir.glob("session_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:limit]
        
        for file_path in session_files:
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    session = SessionState.from_storage(data)
                    self.active_sessions[session.session_id] = session
            except Exception as e:
                logger.error(f"Failed to load session {file_path}: {e}")
    
    async def create_session(self, initial_query: Optional[str] = None) -> SessionState:
        """새 세션 생성"""
        session = SessionState()
        
        if initial_query:
            # 자동 제목 생성 (핵심 명사 추출)
            session.title_auto = self._generate_title(initial_query)
            session.messages.append({
                "role": "user",
                "content": initial_query,
                "timestamp": datetime.now().isoformat()
            })
        
        self.active_sessions[session.session_id] = session
        await self._persist_session(session)
        return session
    
    async def get_session(self, session_id: str) -> Optional[SessionState]:
        """세션 조회"""
        # 메모리에서 먼저 확인
        if session_id in self.active_sessions:
            return self.active_sessions[session_id]
        
        # 파일에서 로드
        session_path = self.storage_dir / f"session_{session_id}.json"
        if session_path.exists():
            try:
                async with aiofiles.open(session_path, 'r', encoding='utf-8') as f:
                    data = json.loads(await f.read())
                    session = SessionState.from_storage(data)
                    self.active_sessions[session_id] = session
                    return session
            except Exception as e:
                logger.error(f"Failed to load session {session_id}: {e}")
        
        return None
    
    async def update_session(self, session_id: str, **updates) -> Optional[SessionState]:
        """세션 업데이트"""
        session = await self.get_session(session_id)
        if not session:
            return None
        
        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        session.updated_at = datetime.now()
        await self._persist_session(session)
        return session
    
    async def add_message(self, session_id: str, role: str, content: str, 
                         citations: Optional[List] = None,
                         carry_over_facts: Optional[str] = None) -> Optional[SessionState]:
        """메시지 추가"""
        session = await self.get_session(session_id)
        if not session:
            return None
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "turn_id": str(uuid.uuid4())
        }
        
        if citations:
            message["citations"] = citations
        
        session.messages.append(message)
        
        # carry-over facts 업데이트
        if carry_over_facts:
            session.carry_over_facts = carry_over_facts
        
        # 첫 응답 후 자동 제목 생성
        if len(session.messages) == 2 and not session.title_auto:
            session.title_auto = self._generate_title(content)
        
        session.updated_at = datetime.now()
        await self._persist_session(session)
        return session
    
    async def update_draft(self, session_id: str, draft_data: Dict):
        """초안 상태 업데이트 (스트리밍 중)"""
        draft = self.draft_cache.get(session_id)
        if not draft:
            draft = DraftState(session_id=session_id, **draft_data)
            self.draft_cache[session_id] = draft
        else:
            for key, value in draft_data.items():
                if hasattr(draft, key):
                    setattr(draft, key, value)
        
        # 200토큰마다 강제 저장
        if draft.partial_tokens and len(draft.partial_tokens) % 200 == 0:
            await self._persist_draft(session_id, draft)
    
    async def resume_session(self, session_id: str) -> Optional[Dict]:
        """중단된 세션 재개 정보"""
        # 초안 확인
        draft_path = self.storage_dir / f"draft_{session_id}.json"
        if draft_path.exists():
            try:
                async with aiofiles.open(draft_path, 'r', encoding='utf-8') as f:
                    draft_data = json.loads(await f.read())
                    return {
                        "session_id": session_id,
                        "resume_from": "draft",
                        "draft_state": draft_data
                    }
            except Exception as e:
                logger.error(f"Failed to load draft {session_id}: {e}")
        
        # 세션 확인
        session = await self.get_session(session_id)
        if session and session.pending_request:
            return {
                "session_id": session_id,
                "resume_from": "pending",
                "pending_request": session.pending_request,
                "carry_over_facts": session.carry_over_facts
            }
        
        return None
    
    async def list_sessions(self, limit: int = 50, cursor: Optional[str] = None,
                           archived: bool = False) -> Dict:
        """세션 목록 조회"""
        all_sessions = list(self.active_sessions.values())
        
        # 아카이브 필터
        filtered = [s for s in all_sessions if s.archived == archived]
        
        # 정렬 (최신순)
        filtered.sort(key=lambda s: s.updated_at, reverse=True)
        
        # 페이지네이션
        start_idx = 0
        if cursor:
            for i, s in enumerate(filtered):
                if s.session_id == cursor:
                    start_idx = i + 1
                    break
        
        page_sessions = filtered[start_idx:start_idx + limit]
        next_cursor = page_sessions[-1].session_id if len(page_sessions) == limit else None
        
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "title": s.title,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                    "message_count": len(s.messages),
                    "archived": s.archived
                }
                for s in page_sessions
            ],
            "next_cursor": next_cursor,
            "total": len(filtered)
        }
    
    async def search_sessions(self, query: str, limit: int = 20) -> List[Dict]:
        """세션 검색"""
        results = []
        query_lower = query.lower()
        
        for session in self.active_sessions.values():
            # 제목 검색
            if session.title and query_lower in session.title.lower():
                results.append(session)
                continue
            
            # 메시지 내용 검색
            for msg in session.messages:
                if query_lower in msg.get("content", "").lower():
                    results.append(session)
                    break
        
        # 관련도 점수 계산
        for session in results:
            score = 0
            if session.title and query_lower in session.title.lower():
                score += 10
            for msg in session.messages:
                if query_lower in msg.get("content", "").lower():
                    score += 1
            session._search_score = score
        
        # 점수순 정렬
        results.sort(key=lambda s: s._search_score, reverse=True)
        
        return [
            {
                "session_id": s.session_id,
                "title": s.title,
                "updated_at": s.updated_at.isoformat(),
                "match_preview": self._get_match_preview(s, query_lower)
            }
            for s in results[:limit]
        ]
    
    async def delete_session(self, session_id: str) -> bool:
        """세션 삭제"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        # 파일 삭제
        session_path = self.storage_dir / f"session_{session_id}.json"
        draft_path = self.storage_dir / f"draft_{session_id}.json"
        
        deleted = False
        if session_path.exists():
            session_path.unlink()
            deleted = True
        if draft_path.exists():
            draft_path.unlink()
        
        return deleted
    
    async def _persist_session(self, session: SessionState):
        """세션을 파일시스템에 저장"""
        session_path = self.storage_dir / f"session_{session.session_id}.json"
        try:
            async with aiofiles.open(session_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(session.to_storage(), 
                                        ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Failed to persist session {session.session_id}: {e}")
    
    def _generate_title(self, text: str, max_length: int = 20) -> str:
        """자동 제목 생성 (핵심 명사 추출)"""
        import re
        
        # 너무 짧은 텍스트는 처리 안함
        if len(text) < 5:
            return "새 대화"
        
        # 한국어 명사 패턴 (간단한 휴리스틱)
        nouns = re.findall(r'[가-힣]{2,}(?:시스템|서비스|정책|규정|절차|방법|기준|지침|보고서|분석|평가|계획|전략|목표|성과|결과|현황|동향|전망|예측|대응|개선|혁신|지원|관리|운영|추진|시행|검토|협의|논의|회의|안건|사항|문제|이슈|과제|해결|방안|대책|조치|통계|데이터|정보|자료|문서|양식|서식|신청|접수|처리|승인|결재|통보|안내|공지|홍보|교육|연수|평가|심사|감사|점검|모니터링|피드백|예술촌|문화)', text)
        
        # 일반 명사 패턴 (중요 단어)
        if not nouns:
            nouns = re.findall(r'[가-힣]{3,}', text)
            nouns = [n for n in nouns if len(n) >= 3]  # 3자 이상만
        
        if nouns:
            # 가장 긴 명사 2개 선택
            nouns = sorted(set(nouns), key=len, reverse=True)[:2]
            title = " ".join(nouns)
        else:
            # 공백으로 분리하여 처음 몇 단어 사용
            words = text.split()
            title = " ".join(words[:5])[:max_length].strip()
            if len(title) < 5:
                title = text[:max_length].strip()
            if len(text) > max_length:
                title += "..."
        
        # 최종 검증 - 너무 짧으면 원문 사용
        if len(title) < 3:
            title = text[:max_length].strip()
        
        return title[:max_length]
    
    def _get_match_preview(self, session: SessionState, query: str, context_length: int = 50) -> str:
        """검색 일치 미리보기"""
        for msg in session.messages:
            content = msg.get("content", "")
            idx = content.lower().find(query)
            if idx != -1:
                start = max(0, idx - context_length)
                end = min(len(content), idx + len(query) + context_length)
                preview = content[start:end]
                if start > 0:
                    preview = "..." + preview
                if end < len(content):
                    preview = preview + "..."
                return preview
        return ""

# 전역 세션 관리자 인스턴스
session_manager = SessionManager()