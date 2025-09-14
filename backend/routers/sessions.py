"""
Sessions API Router
세션 관리, 대화 히스토리, 스트리밍 제어 엔드포인트
"""

from fastapi import APIRouter, HTTPException, Query, Body, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Optional, Dict, List, Any
from datetime import datetime
import json
import asyncio
import uuid
from pydantic import BaseModel, Field

from backend.session_manager import session_manager
from backend.rag.generator_ollama import OllamaGenerator
from backend.rag.hybrid_retriever import HybridRetriever
from backend.rag.answer_formatter import AnswerFormatter
from backend.config import config
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# Request/Response Models
class CreateSessionRequest(BaseModel):
    initial_query: Optional[str] = None

class UpdateSessionRequest(BaseModel):
    title_user: Optional[str] = None
    archived: Optional[bool] = None

class MessageRequest(BaseModel):
    content: str
    session_id: Optional[str] = None
    stream: bool = True
    resume_token: Optional[str] = None

class AbortRequest(BaseModel):
    session_id: str
    turn_id: str

# 활성 스트리밍 연결 추적
active_streams: Dict[str, asyncio.Task] = {}
abort_signals: Dict[str, asyncio.Event] = {}

@router.post("/create")
async def create_session(request: CreateSessionRequest):
    """새 세션 생성"""
    session = await session_manager.create_session(request.initial_query)
    return {
        "session_id": session.session_id,
        "title": session.title,
        "created_at": session.created_at.isoformat()
    }

@router.get("/list")
async def list_sessions(
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = Query(None),
    archived: bool = Query(False)
):
    """세션 목록 조회"""
    return await session_manager.list_sessions(limit, cursor, archived)

@router.get("/search")
async def search_sessions(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=50)
):
    """세션 검색"""
    results = await session_manager.search_sessions(q, limit)
    return {"results": results, "query": q, "total": len(results)}

@router.get("/{session_id}")
async def get_session(session_id: str):
    """세션 상세 조회"""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session.session_id,
        "title": session.title,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "messages": session.messages,
        "carry_over_facts": session.carry_over_facts,
        "archived": session.archived
    }

@router.patch("/{session_id}")
async def update_session(session_id: str, request: UpdateSessionRequest):
    """세션 메타데이터 업데이트"""
    updates = request.model_dump(exclude_unset=True)
    session = await session_manager.update_session(session_id, **updates)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session.session_id,
        "title": session.title,
        "updated": True
    }

@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """세션 삭제"""
    deleted = await session_manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"deleted": True}

@router.post("/message")
async def send_message(request: MessageRequest, background_tasks: BackgroundTasks):
    """메시지 전송 및 응답 생성"""
    
    # 세션 확인/생성
    session_id = request.session_id
    if not session_id:
        session = await session_manager.create_session(request.content)
        session_id = session.session_id
    else:
        session = await session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # 사용자 메시지 추가
        await session_manager.add_message(session_id, "user", request.content)
    
    # 턴 ID 생성
    turn_id = str(uuid.uuid4())
    
    # 스트리밍 응답
    if request.stream:
        return StreamingResponse(
            stream_response(
                session_id=session_id,
                turn_id=turn_id,
                query=request.content,
                carry_over_facts=session.carry_over_facts,
                resume_token=request.resume_token
            ),
            media_type="text/event-stream"
        )
    else:
        # 동기 응답
        response = await generate_response(
            session_id=session_id,
            turn_id=turn_id,
            query=request.content,
            carry_over_facts=session.carry_over_facts,
            resume_token=request.resume_token
        )
        
        # 응답 저장
        await session_manager.add_message(
            session_id,
            "assistant",
            response["answer"],
            citations=response.get("citations"),
            carry_over_facts=response.get("carry_over", {}).get("facts")
        )
        
        return response

async def stream_response(session_id: str, turn_id: str, query: str, 
                         carry_over_facts: Optional[str] = None,
                         resume_token: Optional[str] = None):
    """SSE 스트리밍 응답 생성"""
    
    # 중단 시그널 설정
    abort_signal = asyncio.Event()
    abort_signals[f"{session_id}:{turn_id}"] = abort_signal
    
    try:
        # 검색 수행
        retriever = HybridRetriever()
        evidences = retriever.retrieve(query, limit=5)
        
        # 생성기 초기화
        generator = OllamaGenerator()
        formatter = AnswerFormatter()
        
        # 기존 RAG 시스템의 generate 메서드 사용 (올바른 프롬프트 템플릿)
        # 먼저 비스트리밍으로 생성
        response = await generator.generate(
            query=query,
            evidences=evidences,
            stream=False,
            carry_over_facts=carry_over_facts,
            resume_token=resume_token
        )
        
        # 포맷팅
        formatted = formatter.format_response(
            response,
            session_id=session_id,
            turn_id=turn_id,
            carry_over_facts=carry_over_facts
        )
        
        # 응답을 토큰 단위로 스트리밍 (시뮬레이션)
        answer_text = formatted.get("answer", "")
        token_count = 0
        
        # 답변을 문자 단위로 스트리밍
        for i, char in enumerate(answer_text):
            if abort_signal.is_set():
                yield f"data: {json.dumps({'type': 'abort', 'partial': answer_text[:i], 'resume_token': generate_resume_token(answer_text[:i])}, ensure_ascii=False)}\n\n"
                break
            
            yield f"data: {json.dumps({'type': 'token', 'content': char}, ensure_ascii=False)}\n\n"
            token_count += 1
            
            # 200자마다 초안 저장
            if token_count % 200 == 0:
                await session_manager.update_draft(session_id, {
                    "partial_tokens": answer_text[:i+1],
                    "pending_request": {
                        "query": query,
                        "start_ts": datetime.now().isoformat(),
                        "partial_tokens": answer_text[:i+1]
                    }
                })
            
            # 스트리밍 속도 조절
            await asyncio.sleep(0.01)
        
        # 완료 시
        if not abort_signal.is_set():
            
            # carry-over facts 생성
            carry_over_facts_new = generate_carry_over_facts(formatted.get("answer", answer_text), evidences)
            
            # 세션 가져오기 (title_auto 생성용)
            session = await session_manager.get_session(session_id)
            
            # 세션에 저장
            await session_manager.add_message(
                session_id,
                "assistant",
                formatted["answer"],
                citations=formatted.get("sources"),
                carry_over_facts=carry_over_facts_new
            )
            
            # 메타데이터 포함 최종 응답
            final_response = {
                **formatted,
                "meta": {
                    "session_id": session_id,
                    "turn_id": turn_id,
                    "resume_token": None,
                    "is_partial": False,
                    "title_auto": generate_auto_title(query) if session and len(session.messages) <= 2 else None
                },
                "carry_over": {
                    "facts": carry_over_facts_new
                },
                "audit": {
                    "used_session_facts": bool(carry_over_facts),
                    "citations_sequential": True,
                    "language_purity_ko_only": True
                },
                "ui_hints": {
                    "list_update": True,
                    "can_interrupt": False,
                    "autosave_suggested": False
                }
            }
            
            yield f"data: {json.dumps({'type': 'complete', 'response': final_response}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'}, ensure_ascii=False)}\n\n"
    
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
    
    finally:
        # 정리
        abort_key = f"{session_id}:{turn_id}"
        if abort_key in abort_signals:
            del abort_signals[abort_key]
        if abort_key in active_streams:
            del active_streams[abort_key]

@router.post("/abort")
async def abort_generation(request: AbortRequest):
    """생성 중단"""
    abort_key = f"{request.session_id}:{request.turn_id}"
    
    if abort_key in abort_signals:
        abort_signals[abort_key].set()
        return {"aborted": True}
    
    return {"aborted": False, "reason": "No active generation"}

@router.post("/resume/{session_id}")
async def resume_session(session_id: str):
    """중단된 세션 재개"""
    resume_info = await session_manager.resume_session(session_id)
    
    if not resume_info:
        raise HTTPException(status_code=404, detail="No resumable state found")
    
    return resume_info

@router.post("/draft/save")
async def save_draft(session_id: str = Body(...), draft_data: Dict = Body(...)):
    """초안 저장 (클라이언트 트리거)"""
    await session_manager.update_draft(session_id, draft_data)
    return {"saved": True}

# Helper functions
async def generate_response(session_id: str, turn_id: str, query: str,
                           carry_over_facts: Optional[str] = None,
                           resume_token: Optional[str] = None) -> Dict:
    """동기식 응답 생성"""
    retriever = HybridRetriever()
    generator = OllamaGenerator()
    formatter = AnswerFormatter()
    
    # 검색
    evidences = retriever.retrieve(query, limit=5)
    
    # 생성 (기존 RAG 시스템 사용)
    response = await generator.generate(
        query=query,
        evidences=evidences,
        stream=False
    )
    
    # 포맷팅
    formatted = formatter.format_response(
        response,
        session_id=session_id,
        turn_id=turn_id,
        carry_over_facts=carry_over_facts
    )
    
    # carry-over facts 생성
    carry_over_facts_new = generate_carry_over_facts(formatted.get("answer", ""), evidences)
    
    return {
        **formatted,
        "meta": {
            "session_id": session_id,
            "turn_id": turn_id,
            "resume_token": None,
            "is_partial": False
        },
        "carry_over": {
            "facts": carry_over_facts_new
        }
    }

def generate_resume_token(partial_text: str) -> str:
    """재개 토큰 생성"""
    import hashlib
    return hashlib.md5(partial_text.encode()).hexdigest()[:8]

def generate_carry_over_facts(response: str, evidences: List[Dict], max_length: int = 500) -> str:
    """다음 턴을 위한 facts 요약 (300-500자)"""
    facts = []
    
    # 응답에서 핵심 문장 추출
    sentences = response.split('.')[:5]  # 상위 5문장
    for sent in sentences:
        if len(sent.strip()) > 20:  # 의미있는 문장만
            facts.append(sent.strip())
    
    # 증거에서 핵심 정보 추출
    for evidence in evidences[:2]:  # 상위 2개 증거
        if evidence.get("text_snippet"):
            snippet = evidence["text_snippet"][:100]
            facts.append(f"[출처: {evidence.get('doc_id', 'Unknown')}] {snippet}")
    
    # 요약 생성
    summary = " ".join(facts)[:max_length]
    
    return summary

def generate_auto_title(query: str, max_length: int = 20) -> str:
    """자동 제목 생성"""
    import re
    
    # 핵심 명사 추출
    keywords = re.findall(r'[가-힣]+(?:시스템|정책|규정|방법|지침|분석|계획|관리|서비스)', query)
    
    if keywords:
        title = " ".join(keywords[:2])[:max_length]
    else:
        title = query[:max_length].strip()
        if len(query) > max_length:
            title += "..."
    
    return title