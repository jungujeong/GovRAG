from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query, Request
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional, Any
import asyncio
import json
import logging
from datetime import datetime
from starlette.requests import ClientDisconnect

from schemas import QueryRequest, QueryResponse
from models.session import ChatSession, Message
from services.session_manager import session_manager
from rag.hybrid_retriever import HybridRetriever
from rag.reranker import Reranker
from rag.generator_ollama import OllamaGenerator
from rag.evidence_enforcer import EvidenceEnforcer
from rag.citation_tracker import CitationTracker
from rag.answer_formatter import AnswerFormatter
from config import config
from utils.error_handler import ErrorHandler
from utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

router = APIRouter()

# Component initialization
retriever = HybridRetriever()
reranker = Reranker()
generator = OllamaGenerator()
enforcer = EvidenceEnforcer()
citation_tracker = CitationTracker()
formatter = AnswerFormatter()
error_handler = ErrorHandler()
rate_limiter = RateLimiter(max_requests=30, window_seconds=60)

# WebSocket connections management
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_locks: Dict[str, asyncio.Lock] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket
        if session_id not in self.session_locks:
            self.session_locks[session_id] = asyncio.Lock()
        logger.info(f"WebSocket connected for session {session_id}")
    
    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        logger.info(f"WebSocket disconnected for session {session_id}")
    
    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            try:
                await self.active_connections[session_id].send_json(message)
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {e}")
    
    async def broadcast_to_session(self, session_id: str, message: dict):
        await self.send_message(session_id, message)

manager = ConnectionManager()

# Session endpoints
from pydantic import BaseModel

class CreateSessionRequest(BaseModel):
    title: Optional[str] = None
    document_ids: Optional[List[str]] = None

@router.post("/sessions")
async def create_session(request: CreateSessionRequest) -> Dict:
    """새 채팅 세션 생성"""
    try:
        session = await session_manager.create_session(request.title, _normalize_doc_ids(request.document_ids))
        return {
            "success": True,
            "session": session.to_dict()
        }
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail="세션 생성에 실패했습니다")

@router.get("/sessions")
async def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
) -> Dict:
    """세션 목록 조회"""
    try:
        session_list = await session_manager.list_sessions(page, page_size)
        return {
            "success": True,
            "sessions": session_list.sessions,
            "total": session_list.total,
            "page": session_list.page,
            "page_size": session_list.page_size
        }
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail="세션 목록 조회에 실패했습니다")

@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> Dict:
    """특정 세션 조회"""
    try:
        session = await session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        return {
            "success": True,
            "session": session.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="세션 조회에 실패했습니다")

class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    document_ids: Optional[List[str]] = None

@router.put("/sessions/{session_id}")
async def update_session(
    session_id: str,
    request: UpdateSessionRequest
) -> Dict:
    """세션 정보 업데이트"""
    try:
        session = await session_manager.update_session(session_id, request.title, _normalize_doc_ids(request.document_ids))
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        return {
            "success": True,
            "session": session.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="세션 업데이트에 실패했습니다")

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> Dict:
    """세션 삭제"""
    try:
        success = await session_manager.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        return {
            "success": True,
            "message": "세션이 삭제되었습니다"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="세션 삭제에 실패했습니다")

# Chat endpoints
@router.post("/sessions/{session_id}/messages")
async def send_message(
    session_id: str,
    request: QueryRequest,
    http_request: Request
) -> QueryResponse:
    """세션에 메시지 전송 및 응답 생성"""
    
    # 연결 상태 체크 (항상 활성화)
    cancelled = False
    cancel_event = asyncio.Event()

    async def check_client_disconnect():
        nonlocal cancelled
        try:
            while not cancelled:
                try:
                    if await http_request.is_disconnected():
                        cancelled = True
                        cancel_event.set()
                        logger.info(f"Client disconnected for session {session_id}")
                        # 중단 메시지를 세션에 저장 (중복 저장 방지: 최근 메시지 확인은 클라이언트에서 처리)
                        await session_manager.add_message(
                            session_id,
                            "assistant",
                            "답변 생성이 중단되었습니다. 페이지가 새로고침되었거나 요청이 취소되었습니다.",
                            metadata={"interrupted": True, "reason": "client_disconnect"}
                        )
                        break
                except Exception as e:
                    logger.debug(f"Error checking disconnect: {e}")
                    break
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            # 정상 취소
            pass

    disconnect_task = asyncio.create_task(check_client_disconnect())
    
    try:
        # Rate limiting
        if not await rate_limiter.check_limit(session_id):
            raise HTTPException(status_code=429, detail="너무 많은 요청입니다. 잠시 후 다시 시도해 주세요")
        
        # Session validation
        session = await session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        # Input validation
        if not request.query or not request.query.strip():
            # 질문이 입력되지 않은 경우 - 출처 없이 간단한 안내 메시지만 반환
            await session_manager.add_message(
                session_id,
                "assistant",
                "질문을 입력해 주시면 답변을 드리겠습니다.",
                sources=[]  # 출처 없음
            )
            return QueryResponse(
                query="",
                answer="질문을 입력해 주시면 답변을 드리겠습니다.",
                key_facts=[],
                sources=[],  # 출처 없음
                session_id=session_id
            )
        
        if len(request.query) > 2000:
            raise HTTPException(status_code=400, detail="메시지가 너무 깁니다. 짧게 나누어 보내주세요")
        
        # Check if documents are uploaded
        if not session.document_ids and not request.skip_document_check:
            raise HTTPException(
                status_code=400,
                detail="먼저 문서를 업로드해 주세요",
                headers={"X-Error-Type": "NO_DOCUMENTS"}
            )
        
        # Add user message
        await session_manager.add_message(session_id, "user", request.query)
        
        # Get conversation context
        context = await session_manager.get_session_context(session_id, max_messages=10)
        
        # Process query with RAG
        try:
            # 1. Retrieve with document filtering
            logger.info(f"Retrieving for query: {request.query}")
            logger.info(f"Session document IDs: {session.document_ids}")

            evidences = retriever.retrieve(
                request.query,
                limit=config.TOPK_BM25 + config.TOPK_VECTOR,
                document_ids=session.document_ids if session.document_ids else None
            )

            logger.info(f"Retrieved {len(evidences)} evidences")

            # Do not fall back to unfiltered retrieval; enforce session document scope strictly
            
            # 클라이언트 연결이 끊겼다면 즉시 중단
            if cancel_event.is_set():
                raise HTTPException(status_code=499, detail="Client closed request")

            if not evidences:
                response_text = "업로드된 문서에서 해당 정보를 찾을 수 없습니다."
                await session_manager.add_message(
                    session_id, 
                    "assistant", 
                    response_text,
                    error="no_evidence"
                )
                return QueryResponse(
                    query=request.query,
                    answer=response_text,
                    key_facts=[],
                    sources=[],
                    error="no_evidence",
                    session_id=session_id
                )
            
            # 2. Rerank if available
            if reranker.model or (reranker.use_onnx and hasattr(reranker, 'ort_session')):
                evidences = reranker.rerank(
                    request.query,
                    evidences,
                    top_k=config.TOPK_RERANK
                )
            else:
                evidences = evidences[:config.TOPK_RERANK]
            
            # 클라이언트 연결이 끊겼다면 즉시 중단
            if cancel_event.is_set():
                raise HTTPException(status_code=499, detail="Client closed request")

            # 3. Generate with context (취소 가능 태스크로 실행)
            gen_task = asyncio.create_task(
                generator.generate_with_context(
                    request.query,
                    evidences,
                    context=context,
                    stream=False
                )
            )

            # cancel_event 와 경합
            cancel_wait = asyncio.create_task(cancel_event.wait())
            done, pending = await asyncio.wait({gen_task, cancel_wait}, return_when=asyncio.FIRST_COMPLETED)
            
            # 정리
            cancel_wait.cancel()

            if gen_task in done:
                response = gen_task.result()
                # Sanitize any think tags from non-streamed content
                def strip_think_sections(text: str) -> str:
                    if not isinstance(text, str) or not text:
                        return text
                    try:
                        import re
                        patterns = [
                            r'(?is)<think>.*?</think>',
                            r'(?is)<thinking>.*?</thinking>',
                            r'(?is)\[think\].*?\[/think\]'
                        ]
                        for p in patterns:
                            text = re.sub(p, '', text)
                        # Remove any stray residual tags
                        text = re.sub(r'(?is)</?thinking?>', '', text)
                        text = re.sub(r'(?is)\[/?think\]', '', text)
                        return text.strip()
                    except Exception:
                        return text
                if isinstance(response, dict):
                    if 'answer' in response:
                        response['answer'] = strip_think_sections(response.get('answer', ''))
                    if 'details' in response:
                        response['details'] = strip_think_sections(response.get('details', ''))
            else:
                # 취소 발생: 생성 태스크 취소
                gen_task.cancel()
                try:
                    await gen_task
                except asyncio.CancelledError:
                    pass
                raise HTTPException(status_code=499, detail="Client closed request")
            
            # 4. Verify and enforce evidence
            response = enforcer.enforce_evidence(response, evidences)
            
            # 5. Track citations
            response = citation_tracker.track_citations(response, evidences)
            
            # 6. Format response
            response = formatter.format_response(response)
            
            # Add assistant message
            await session_manager.add_message(
                session_id,
                "assistant",
                response.get("formatted_text", response.get("answer", "")),
                sources=response.get("sources", [])
            )
            
            return QueryResponse(
                query=request.query,
                answer=response.get("answer", ""),
                key_facts=response.get("key_facts", []),
                details=response.get("details", ""),
                sources=response.get("sources", []),
                formatted_text=response.get("formatted_text", ""),
                formatted_html=response.get("formatted_html", ""),
                formatted_markdown=response.get("formatted_markdown", ""),
                confidence=response.get("verification", {}).get("confidence", 0),
                session_id=session_id,
                metadata={
                    "evidence_count": len(evidences),
                    "hallucination_detected": response.get("verification", {}).get("hallucination_detected", False),
                    "context_messages": len(context)
                }
            )
            
        except asyncio.CancelledError:
            # 취소된 경우 이미 중단 메시지가 저장되었으므로 추가 처리 불필요
            logger.info(f"Request cancelled for session {session_id}")
            raise HTTPException(status_code=499, detail="Client closed request")
        except Exception as e:
            if not cancelled:
                error_msg = error_handler.handle_rag_error(e)
                await session_manager.add_message(
                    session_id,
                    "assistant",
                    error_msg,
                    error=str(e)
                )
                raise HTTPException(status_code=500, detail=error_msg)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Message processing failed: {e}")
        if not cancelled:
            error_msg = "죄송합니다. 메시지 처리 중 오류가 발생했습니다. 다시 시도해 주세요."
            await session_manager.add_message(
                session_id,
                "assistant",
                error_msg,
                error=str(e)
            )
            raise HTTPException(status_code=500, detail=error_msg)
    finally:
        # 연결 체크 태스크 종료
        cancelled = True
        if disconnect_task:
            disconnect_task.cancel()
            try:
                await disconnect_task
            except asyncio.CancelledError:
                pass

@router.post("/sessions/{session_id}/messages/stream")
async def send_message_stream(
    session_id: str,
    request: QueryRequest,
    http_request: Request
):
    """스트리밍 응답으로 메시지 처리"""
    cancel_event = asyncio.Event()
    interrupt_recorded = False

    async def monitor_disconnect():
        nonlocal interrupt_recorded
        try:
            while not cancel_event.is_set():
                if await http_request.is_disconnected():
                    logger.info(f"[stream] Client disconnected for session {session_id}")
                    cancel_event.set()
                    if not interrupt_recorded:
                        try:
                            await session_manager.add_message(
                                session_id,
                                "assistant",
                                "답변 생성이 중단되었습니다.",
                                metadata={"interrupted": True, "reason": "client_disconnect"}
                            )
                            interrupt_recorded = True
                        except Exception as e:
                            logger.error(f"Failed to record interrupt on disconnect: {e}")
                    break
                await asyncio.sleep(0.25)
        except Exception as e:
            logger.debug(f"monitor_disconnect error: {e}")

    monitor_task = asyncio.create_task(monitor_disconnect())

    async def generate():
        full_response = ""
        # Streaming-time think-tag filter state
        in_think = False
        pending = ""
        start_tags = [("<think>", 7), ("<thinking>", 11), ("[think]", 7)]
        end_tags = [("</think>", 8), ("</thinking>", 12), ("[/think]", 8)]

        def find_any(haystack_lower, tags):
            idx = -1
            tag_len = 0
            for t, tlen in tags:
                i = haystack_lower.find(t)
                if i != -1 and (idx == -1 or i < idx):
                    idx = i
                    tag_len = tlen
            return idx, tag_len

        try:
            # Session validation
            session = await session_manager.get_session(session_id)
            if not session:
                yield json.dumps({"error": "세션을 찾을 수 없습니다"}) + "\n"
                return
            
            # Add user message
            await session_manager.add_message(session_id, "user", request.query)
            
            # Send status update
            yield json.dumps({"status": "문서 검색 중..."}) + "\n"
            
            # Get context and evidences
            context = await session_manager.get_session_context(session_id)
            evidences = retriever.retrieve(
                request.query,
                document_ids=session.document_ids if session.document_ids else None
            )
            
            if cancel_event.is_set():
                return
            
            if not evidences:
                yield json.dumps({
                    "error": "no_evidence",
                    "message": "업로드된 문서에서 해당 정보를 찾을 수 없습니다."
                }) + "\n"
                return
            
            # Send status update
            yield json.dumps({"status": "답변 생성 중..."}) + "\n"
            
            # Rerank if available
            if reranker.model:
                evidences = reranker.rerank(request.query, evidences)[:config.TOPK_RERANK]
            else:
                evidences = evidences[:config.TOPK_RERANK]
            
            # Stream generation with explicit generator handle for clean aclose
            agen = generator.stream_with_context(
                request.query,
                evidences,
                context=context,
                cancel_event=cancel_event
            )
            try:
                async for chunk in agen:
                    if cancel_event.is_set():
                        break
                    if not chunk:
                        continue
                    # Append and filter think sections
                    pending += chunk
                    while True:
                        lbuf = pending.lower()
                        if not in_think:
                            s_idx, s_len = find_any(lbuf, start_tags)
                            if s_idx != -1:
                                # Emit content before <think>
                                if s_idx > 0:
                                    emit = pending[:s_idx]
                                    if emit:
                                        full_response += emit
                                        yield json.dumps({"content": emit}) + "\n"
                                # Enter think region
                                pending = pending[s_idx + s_len:]
                                in_think = True
                                continue
                            else:
                                # No start tag; emit safe prefix keeping small tail to catch split tags
                                tail = 16
                                if len(pending) > tail:
                                    emit = pending[:-tail]
                                    pending = pending[-tail:]
                                    if emit:
                                        full_response += emit
                                        yield json.dumps({"content": emit}) + "\n"
                                break
                        else:
                            # Inside think; look for any end tag
                            e_idx, e_len = find_any(lbuf, end_tags)
                            if e_idx != -1:
                                # Drop up to end tag, exit think
                                pending = pending[e_idx + e_len:]
                                in_think = False
                                continue
                            else:
                                # Still inside think; keep buffer bounded and wait for more
                                if len(pending) > 8192:
                                    pending = pending[-4096:]
                                break
            finally:
                try:
                    await agen.aclose()
                except Exception:
                    pass

            # Flush ALL remaining pending content (important for complete response)
            if not cancel_event.is_set() and pending:
                # If we're still in think mode, we should NOT emit the content
                if not in_think:
                    emit = pending
                    pending = ""
                    if emit:
                        full_response += emit
                        yield json.dumps({"content": emit}) + "\n"
            
            if cancel_event.is_set():
                # 이미 monitor_disconnect에서 중단 메시지를 기록했을 수 있음
                if not interrupt_recorded:
                    try:
                        await session_manager.add_message(
                            session_id,
                            "assistant",
                            "답변 생성이 중단되었습니다.",
                            metadata={"interrupted": True, "reason": "client_disconnect"}
                        )
                        interrupt_recorded = True
                    except Exception as e:
                        logger.error(f"Failed to record interrupt after cancel: {e}")
                return

            # Process citations
            response_data = citation_tracker.track_citations(
                {"answer": full_response},
                evidences
            )
            # Filter to only truly cited/matched sources
            try:
                response_data = formatter._filter_cited_sources(response_data)
            except Exception:
                pass
            
            # Save complete message
            await session_manager.add_message(
                session_id,
                "assistant",
                full_response,
                sources=response_data.get("sources", [])
            )
            
            # Send final data with sources
            yield json.dumps({
                "complete": True,
                "sources": response_data.get("sources", [])
            }) + "\n"
            
        except ClientDisconnect:
            # 클라이언트 연결 종료: 중단 메시지 저장 후 종료
            try:
                await session_manager.add_message(
                    session_id,
                    "assistant",
                    "답변 생성이 중단되었습니다.",
                    metadata={"interrupted": True, "reason": "client_disconnect"}
                )
                interrupt_recorded = True
            except Exception as e:
                logger.error(f"Failed to record interrupt on disconnect: {e}")
            return
        except asyncio.CancelledError:
            # 서버 태스크 취소
            try:
                await session_manager.add_message(
                    session_id,
                    "assistant",
                    "답변 생성이 중단되었습니다.",
                    metadata={"interrupted": True, "reason": "server_cancel"}
                )
            except Exception as e:
                logger.error(f"Failed to record server cancel: {e}")
            return
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            # 에러는 클라이언트에 전송(연결이 살아있을 때만)
            try:
                yield json.dumps({"error": str(e)}) + "\n"
            except Exception:
                pass
        finally:
            try:
                cancel_event.set()
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
            except Exception:
                pass
    
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson"
    )

@router.websocket("/sessions/{session_id}/ws")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket 연결 for real-time chat"""
    await manager.connect(websocket, session_id)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            
            # Process based on message type
            if data.get("type") == "ping":
                await manager.send_message(session_id, {"type": "pong"})
                
            elif data.get("type") == "message":
                query = data.get("content", "")
                
                # Validate input
                if not query.strip():
                    await manager.send_message(session_id, {
                        "type": "error",
                        "message": "메시지를 입력해 주세요"
                    })
                    continue
                
                # Get session
                session = await session_manager.get_session(session_id)
                if not session:
                    await manager.send_message(session_id, {
                        "type": "error",
                        "message": "세션을 찾을 수 없습니다"
                    })
                    continue
                
                # Process with lock to prevent concurrent processing
                async with manager.session_locks.get(session_id, asyncio.Lock()):
                    try:
                        # Add user message
                        await session_manager.add_message(session_id, "user", query)
                        
                        # Send status
                        await manager.send_message(session_id, {
                            "type": "status",
                            "message": "문서 검색 중..."
                        })
                        
                        # Get evidences
                        evidences = retriever.retrieve(query, document_ids=session.document_ids)
                        
                        if not evidences:
                            await manager.send_message(session_id, {
                                "type": "response",
                                "content": "업로드된 문서에서 해당 정보를 찾을 수 없습니다.",
                                "complete": True
                            })
                            continue
                        
                        # Send status
                        await manager.send_message(session_id, {
                            "type": "status",
                            "message": "답변 생성 중..."
                        })
                        
                        # Get context
                        context = await session_manager.get_session_context(session_id)
                        
                        # Stream response
                        full_response = ""
                        async for chunk in generator.stream_with_context(
                            query,
                            evidences,
                            context=context
                        ):
                            if chunk:
                                full_response += chunk
                                await manager.send_message(session_id, {
                                    "type": "response",
                                    "content": chunk,
                                    "complete": False
                                })
                        
                        # Process citations
                        response_data = citation_tracker.track_citations(
                            {"answer": full_response},
                            evidences
                        )
                        
                        # Save complete message
                        await session_manager.add_message(
                            session_id,
                            "assistant",
                            full_response,
                            sources=response_data.get("sources", [])
                        )

                        # Send completion with sources
                        await manager.send_message(session_id, {
                            "type": "response",
                            "complete": True,
                            "sources": response_data.get("sources", [])
                        })
                        
                    except Exception as e:
                        logger.error(f"WebSocket processing error: {e}")
                        await manager.send_message(session_id, {
                            "type": "error",
                            "message": "처리 중 오류가 발생했습니다"
                        })
            
            elif data.get("type") == "stop":
                # Handle stop request
                await manager.send_message(session_id, {
                    "type": "stopped",
                    "message": "답변 생성이 중단되었습니다"
                })
                
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(session_id)

@router.post("/sessions/{session_id}/interrupt")
async def interrupt_session(session_id: str) -> Dict:
    """세션 중단 처리"""
    try:
        # 이미 직전 메시지가 중단으로 기록되어 있으면 중복 기록 방지
        session = await session_manager.get_session(session_id)
        if session and session.messages:
            last = session.messages[-1]
            if (last.metadata and last.metadata.get('interrupted')) or (
                isinstance(last.content, str) and '답변 생성이 중단되었습니다' in last.content
            ):
                return {"success": True, "message": "이미 중단 메시지가 저장되어 있습니다"}

        # 중단 메시지 추가
        await session_manager.add_message(
            session_id,
            "assistant",
            "답변 생성이 중단되었습니다.",
            metadata={"interrupted": True, "reason": "user_action"}
        )
        
        return {
            "success": True,
            "message": "중단 메시지가 저장되었습니다"
        }
    except Exception as e:
        logger.error(f"Failed to save interrupt message: {e}")
        raise HTTPException(status_code=500, detail="중단 처리에 실패했습니다")

@router.delete("/sessions/{session_id}/messages")
async def clear_messages(session_id: str) -> Dict:
    """세션 메시지 초기화"""
    try:
        success = await session_manager.clear_session_messages(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        return {
            "success": True,
            "message": "대화 내역이 초기화되었습니다"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to clear messages: {e}")
        raise HTTPException(status_code=500, detail="메시지 초기화에 실패했습니다")

@router.get("/sessions/{session_id}/export")
async def export_session(session_id: str) -> Dict:
    """세션 내보내기"""
    try:
        session_data = await session_manager.export_session(session_id)
        if not session_data:
            raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다")
        
        return {
            "success": True,
            "session_data": session_data,
            "exported_at": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to export session: {e}")
        raise HTTPException(status_code=500, detail="세션 내보내기에 실패했습니다")
def _normalize_doc_ids(doc_ids: Optional[List[str]]) -> Optional[List[str]]:
    """Normalize document IDs with Unicode normalization"""
    if not doc_ids:
        return doc_ids

    import unicodedata
    normed = []
    for d in doc_ids:
        try:
            if isinstance(d, str):
                # Apply Unicode normalization first
                d = unicodedata.normalize('NFC', d)
                # Keep the original ID as-is to match indexed documents
                # Don't remove extensions here - they should match what was indexed
                normed.append(d)
        except Exception:
            continue
    return normed
