from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query, Request
from fastapi.responses import StreamingResponse
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import json
import logging
from datetime import datetime
from starlette.requests import ClientDisconnect
import re

from schemas import QueryRequest, QueryResponse
from models.session import ChatSession, Message
from services.session_manager import session_manager
from rag.evidence_enforcer import EvidenceEnforcer
from rag.citation_tracker import CitationTracker
from rag.answer_formatter import AnswerFormatter
from rag.response_postprocessor import ResponsePostProcessor
from rag.response_grounder import ResponseGrounder
from rag.conversation_summarizer import ConversationSummarizer
from rag.query_rewriter import QueryRewriter, RewriteContext
from rag.topic_detector import TopicChangeDetector
from rag.doc_scope_resolver import DocScopeResolver, DocScopeResolution
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rag.hybrid_retriever import HybridRetriever
    from rag.reranker import Reranker
    from rag.generator_ollama import OllamaGenerator
from config import config
from utils.error_handler import ErrorHandler
from utils.rate_limiter import RateLimiter
from services.title_generator import TitleGenerator

logger = logging.getLogger(__name__)

router = APIRouter()

# Component initialization (lazy to make testing lightweight)
retriever: Optional[Any] = None
reranker: Optional[Any] = None
generator: Optional[Any] = None
enforcer = EvidenceEnforcer()
citation_tracker = CitationTracker()
formatter = AnswerFormatter()
postprocessor = ResponsePostProcessor()
error_handler = ErrorHandler()
rate_limiter = RateLimiter(max_requests=30, window_seconds=60)
summarizer: Optional[ConversationSummarizer] = None
query_rewriter: Optional[QueryRewriter] = None
title_generator: Optional[TitleGenerator] = None
topic_detector: Optional[TopicChangeDetector] = None
grounder: Optional[ResponseGrounder] = None
doc_scope_resolver: Optional[DocScopeResolver] = None


def get_retriever():
    global retriever
    if retriever is None:
        from rag.hybrid_retriever import HybridRetriever
        retriever = HybridRetriever()
    return retriever


def get_reranker():
    global reranker
    if reranker is None:
        from rag.reranker import Reranker
        reranker = Reranker()
    return reranker


def get_generator():
    global generator
    if generator is None:
        from rag.generator_ollama import OllamaGenerator
        generator = OllamaGenerator()
    return generator


def get_summarizer() -> ConversationSummarizer:
    global summarizer
    if summarizer is None:
        summarizer = ConversationSummarizer()
    return summarizer


def get_query_rewriter() -> QueryRewriter:
    global query_rewriter
    if query_rewriter is None:
        query_rewriter = QueryRewriter()
    return query_rewriter


def get_topic_detector() -> TopicChangeDetector:
    global topic_detector
    if topic_detector is None:
        topic_detector = TopicChangeDetector(
            similarity_threshold=config.TOPIC_SIMILARITY_THRESHOLD,
            retrieval_confidence_threshold=config.TOPIC_CONFIDENCE_THRESHOLD,
            min_score_threshold=config.TOPIC_MIN_SCORE_THRESHOLD
        )
    return topic_detector


def get_response_grounder() -> ResponseGrounder:
    global grounder
    if grounder is None:
        grounder = ResponseGrounder()
    return grounder


def get_doc_scope_resolver() -> DocScopeResolver:
    global doc_scope_resolver
    if doc_scope_resolver is None:
        doc_scope_resolver = DocScopeResolver(get_topic_detector())
    return doc_scope_resolver


def _deduplicate_doc_ids(doc_ids: Optional[List[str]]) -> List[str]:
    if not doc_ids:
        return []
    seen: set = set()
    ordered: List[str] = []
    for doc_id in doc_ids:
        if not doc_id or doc_id in seen:
            continue
        seen.add(doc_id)
        ordered.append(doc_id)
    return ordered


def _extract_unique_doc_ids(evidences: List[Dict[str, Any]]) -> List[str]:
    return _deduplicate_doc_ids([e.get("doc_id") for e in evidences])


def _average_evidence_score(evidences: List[Dict[str, Any]]) -> Optional[float]:
    scores: List[float] = []
    for evidence in evidences:
        for key in ("score", "similarity", "relevance", "hybrid_score", "normalized_score"):
            value = evidence.get(key)
            if isinstance(value, (int, float)):
                score = float(value)
                if score > 1.0 and key in ("score", "similarity", "relevance"):
                    score = score / 100.0
                scores.append(score)
                break
    if not scores:
        return None
    return sum(scores) / len(scores)


def _collect_memory_facts(response: Dict) -> List[Dict[str, str]]:
    """Extract memory snippets from formatted response by citation index."""
    if not response:
        return []

    pattern = re.compile(r'\[(\d+)\]')
    sources = response.get("sources", []) or []

    number_to_doc: Dict[int, Optional[str]] = {}
    for idx, source in enumerate(sources, 1):
        doc_id = source.get("doc_id")
        display = source.get("display_index") or idx
        if doc_id:
            number_to_doc[int(display)] = doc_id

    texts: List[str] = []
    if response.get("answer"):
        texts.extend(response["answer"].split('\n'))
    for fact in response.get("key_facts", []) or []:
        texts.append(fact)
    if response.get("details"):
        texts.extend(response["details"].split('\n'))

    memory: List[Dict[str, str]] = []
    seen: set = set()

    for line in texts:
        stripped = line.strip()
        if not stripped:
            continue
        doc_ids = {
            number_to_doc.get(int(num))
            for num in pattern.findall(stripped)
            if number_to_doc.get(int(num))
        }
        for doc_id in doc_ids:
            key = (doc_id, stripped)
            if key in seen:
                continue
            memory.append({"doc_id": doc_id, "text": stripped})
            seen.add(key)

    return memory


def _build_memory_evidences(session: ChatSession, doc_scope: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Convert stored memory facts into pseudo-evidences."""
    facts = getattr(session, "memory_facts", []) or []
    evidences: List[Dict[str, Any]] = []
    allowed = set(doc_scope) if doc_scope else None

    for idx, fact in enumerate(facts):
        doc_id = fact.get("doc_id")
        text = fact.get("text")
        if not doc_id or not text:
            continue
        if allowed is not None and doc_id not in allowed:
            continue
        evidences.append({
            "text": text,
            "doc_id": doc_id,
            "page": 0,
            "score": 1.5,
            "chunk_id": f"memory-{doc_id}-{idx}",
            "source": "memory"
        })

    return evidences


def _finalize_doc_scope_metadata(
    base: Optional[Dict[str, Any]],
    *,
    mode: str,
    doc_scope_ids: List[str],
    resolved_doc_ids: List[str],
    requested_doc_ids: List[str],
    diagnostics: Optional[Dict[str, Any]] = None,
    average_score: Optional[float] = None,
    topic_change: bool = False,
    topic_reason: Optional[str] = None,
    topic_suggested: Optional[List[str]] = None,
) -> Dict[str, Any]:
    metadata = dict(base or {})
    metadata["mode"] = mode
    metadata["doc_scope"] = mode
    metadata["doc_scope_ids"] = doc_scope_ids
    metadata["resolved_doc_ids"] = resolved_doc_ids
    metadata["requested_doc_ids"] = requested_doc_ids

    if diagnostics:
        metadata["diagnostics"] = diagnostics
    if average_score is not None:
        metadata["average_score"] = average_score
    if topic_change:
        metadata["topic_change_detected"] = True
        if topic_reason:
            metadata["topic_change_reason"] = topic_reason
        if topic_suggested:
            metadata["suggested_doc_ids"] = topic_suggested

    return metadata


def _resolve_evidences(
    *,
    query: str,
    retrieval_query: str,
    retriever_instance,
    requested_doc_ids: List[str],
    session_doc_ids: List[str],
    previous_doc_ids: List[str],
    should_use_previous_sources: bool,
) -> DocScopeResolution:
    resolver = get_doc_scope_resolver()
    return resolver.resolve(
        query=query,
        retrieval_query=retrieval_query,
        retriever=retriever_instance,
        requested_doc_ids=requested_doc_ids,
        session_doc_ids=session_doc_ids,
        previous_doc_ids=previous_doc_ids,
        should_use_previous_sources=should_use_previous_sources,
        topk=config.TOPK_BM25 + config.TOPK_VECTOR,
        allow_topic_expansion=True,
    )


def get_title_generator() -> TitleGenerator:
    global title_generator
    if title_generator is None:
        title_generator = TitleGenerator()
    return title_generator

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
        if not session.document_ids and not getattr(request, "skip_document_check", False):
            raise HTTPException(
                status_code=400,
                detail="먼저 문서를 업로드해 주세요",
                headers={"X-Error-Type": "NO_DOCUMENTS"}
            )
        
        # Add user message
        await session_manager.add_message(session_id, "user", request.query)

        previous_summary = session.conversation_summary or ""

        # Get conversation context
        context = await session_manager.get_session_context(session_id, max_messages=10)

        # 이전 답변의 출처 추적 (첫 번째 assistant 메시지 기준으로 고정)
        previous_sources: List[Dict[str, Any]] = []
        previous_doc_ids: List[str] = []
        first_assistant_found = False

        # reset_context 플래그가 있으면 컨텍스트 초기화
        if request.reset_context:
            session.first_response_evidences = None
            session.first_response_citation_map = None
            logger.info(f"🔄 Context reset requested - clearing first response data")
            # 메타데이터 업데이트
            await session_manager.update_session(
                session_id,
                first_response_evidences=None,
                first_response_citation_map=None,
                metadata={
                    **((session.metadata or {})),
                    "context_reset_at": datetime.now().isoformat()
                }
            )
            first_assistant_found = False
            previous_doc_ids = []
        # 첫 답변의 고정된 evidences에서 문서 범위만 추출 (evidence 자체는 재사용하지 않음)
        elif session.first_response_evidences:
            first_assistant_found = True
            # Extract doc_ids from stored evidences (문서 범위만 사용)
            previous_doc_ids = list(set([
                e.get("doc_id")
                for e in session.first_response_evidences
                if e.get("doc_id")
            ]))
            logger.info(f"Using doc scope from first response: docs: {previous_doc_ids} (will search for new evidences)")
        else:
            # 첫 번째 assistant 메시지의 출처를 찾아서 고정
            for message in session.messages:
                if message.role == "assistant" and message.sources and not first_assistant_found:
                    previous_sources = message.sources
                    previous_doc_ids = [
                        src.get("doc_id")
                        for src in previous_sources
                        if isinstance(src, dict) and src.get("doc_id")
                    ]
                    first_assistant_found = True
                    logger.info(f"Using first assistant message sources: {previous_doc_ids}")
                    break

        # 첫 번째 assistant가 없으면 가장 최근 것을 사용 (폴백)
        if not first_assistant_found:
            for message in reversed(session.messages):
                if message.role == "assistant" and message.sources:
                    previous_sources = message.sources
                    previous_doc_ids = [
                        src.get("doc_id")
                        for src in previous_sources
                        if isinstance(src, dict) and src.get("doc_id")
                    ]
                    logger.info(f"Using recent assistant message sources (fallback): {previous_doc_ids}")
                    break

        # Rewrite query using available memory layers
        recent_for_rewrite = context[-4:] if context else []
        rewrite_context = RewriteContext(
            current_query=request.query,
            recent_messages=recent_for_rewrite,
            summary=previous_summary,
            entities=session.recent_entities or [],
            previous_sources=previous_sources
        )
        rewrite_result = get_query_rewriter().rewrite(rewrite_context)
        retrieval_query = request.query if rewrite_result.used_fallback else rewrite_result.search_query

        # 사용자가 명시적으로 문서를 지정했는지 확인
        requested_doc_ids = []
        if request.doc_ids:
            requested_doc_ids = [doc_id for doc_id in request.doc_ids if doc_id in session.document_ids]
            if not requested_doc_ids:
                raise HTTPException(status_code=400, detail="요청한 문서를 세션에서 찾을 수 없습니다")

        # 사용자가 새로운 대화를 시작하길 원하는 경우 (reset_context=true)
        if request.reset_context:
            # 세션 초기화
            session.first_response_evidences = None
            session.first_response_citation_map = None
            session.recent_source_doc_ids = []
            await session_manager.update_session(
                session_id,
                first_response_evidences=None,
                first_response_citation_map=None,
                recent_source_doc_ids=[]
            )
            logger.info("Context reset requested - clearing previous sources")
            previous_doc_ids = []

        # 이전 답변의 sources를 사용할지 결정
        should_use_previous_sources = bool(previous_doc_ids) and not requested_doc_ids and not request.reset_context
        topic_change_detected = False
        topic_change_reason: Optional[str] = None
        topic_change_suggested: List[str] = []
        doc_scope_metadata: Dict[str, Any] = {}
        allowed_docs_enforce: Optional[List[str]] = None
        doc_scope_ids: List[str] = []

        # Process query with RAG
        try:
            logger.info(f"Retrieving for query: {request.query}")
            logger.info(f"Session document IDs: {session.document_ids}")

            retriever_instance = get_retriever()
            resolution = _resolve_evidences(
                query=request.query,
                retrieval_query=retrieval_query,
                retriever_instance=retriever_instance,
                requested_doc_ids=requested_doc_ids,
                session_doc_ids=session.document_ids or [],
                previous_doc_ids=previous_doc_ids,
                should_use_previous_sources=should_use_previous_sources,
            )

            if resolution.status == "no_evidence":
                response_text = resolution.error_message or "업로드된 문서에서 해당 정보를 찾을 수 없습니다."
                await session_manager.add_message(
                    session_id,
                    "assistant",
                    response_text,
                    error="no_evidence",
                    metadata={"doc_scope": resolution.doc_scope_ids},
                )
                return QueryResponse(
                    query=request.query,
                    answer=response_text,
                    key_facts=[],
                    sources=[],
                    error="no_evidence",
                    session_id=session_id,
                    metadata={"doc_scope": resolution.metadata},
                )

            evidences = resolution.evidences
            doc_scope_metadata = dict(resolution.metadata or {})
            allowed_docs_enforce = resolution.allowed_doc_ids
            topic_change_detected = resolution.topic_change_detected
            topic_change_reason = resolution.topic_change_reason
            topic_change_suggested = resolution.topic_change_suggested or []
            should_use_previous_sources = resolution.allow_fixed_citations
            doc_scope_ids = resolution.doc_scope_ids
            doc_scope_mode = resolution.doc_scope_mode
            doc_scope_mode = resolution.doc_scope_mode
            doc_scope_mode = resolution.doc_scope_mode

            logger.info(
                "Resolved evidence scope: mode=%s, docs=%s, evidences=%d",
                resolution.doc_scope_mode,
                doc_scope_ids,
                len(evidences),
            )

            if resolution.diagnostics:
                logger.debug("Doc scope diagnostics: %s", resolution.diagnostics)


            # 메모리 기능 비활성화 - 출처 일관성 문제 해결을 위해
            # memory_scope = None
            # if requested_doc_ids:
            #     memory_scope = requested_doc_ids
            # elif should_use_previous_sources and previous_doc_ids:
            #     memory_scope = previous_doc_ids

            # memory_evidences = _build_memory_evidences(session, memory_scope)
            # if memory_evidences:
            #     evidences = memory_evidences + evidences
            #     logger.info(f"Prepended {len(memory_evidences)} memory evidences")

            # 메모리 기능 임시 비활성화
            logger.info("Memory evidences disabled for source consistency")

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
            
            # 2. Rerank if available (후속 질문에서도 항상 reranking 수행)
            # 첫 답변 evidences 재사용 로직 제거 - 항상 새로 검색한 evidence를 rerank
            reranker_instance = get_reranker()
            if reranker_instance and (
                reranker_instance.model or (
                    reranker_instance.use_onnx and hasattr(reranker_instance, 'ort_session')
                )
            ):
                evidences = reranker_instance.rerank(
                    retrieval_query,
                    evidences,
                    top_k=config.TOPK_RERANK
                )
                logger.info(f"Reranked {len(evidences)} evidences for query")
            else:
                evidences = evidences[:config.TOPK_RERANK]

            # 2.5 리랭킹 후 후속 질문인 경우 문서 범위 필터링
            if should_use_previous_sources and previous_doc_ids:
                filtered_evidences = []
                for e in evidences:
                    if e.get("doc_id") in previous_doc_ids:
                        filtered_evidences.append(e)
                    else:
                        logger.warning(f"Post-rerank filtering out evidence from unexpected doc: {e.get('doc_id')}")
                evidences = filtered_evidences
                logger.info(f"Post-rerank filter: {len(evidences)} evidences from {previous_doc_ids}")

            # 클라이언트 연결이 끊겼다면 즉시 중단
            if cancel_event.is_set():
                raise HTTPException(status_code=499, detail="Client closed request")

            # 2.6 생성 전 최종 필터링 - 후속 질문인 경우
            if should_use_previous_sources and previous_doc_ids:
                # evidences를 다시 한번 확인
                final_evidences = []
                for e in evidences:
                    doc_id = e.get("doc_id")
                    if doc_id in previous_doc_ids:
                        final_evidences.append(e)
                    else:
                        logger.error(f"Evidence from unexpected document {doc_id} detected and removed")
                evidences = final_evidences
                logger.info(f"Final pre-generation filter: {len(evidences)} evidences from allowed documents")

            # 3. Generate with context (취소 가능 태스크로 실행)
            gen_task = asyncio.create_task(
                get_generator().generate_with_context(
                    request.query,
                    evidences,
                    context=context,
                    doc_scope=doc_scope_metadata,
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
            
            # 4. Ground and verify response (respect resolved scope)
            response = get_response_grounder().ground(response, evidences)
            response = postprocessor.process(response, evidences)

            # 4.1 생성된 response에서 sources 강제 필터링
            if allowed_docs_enforce and "sources" in response:
                original_sources = response.get("sources", [])
                filtered_sources = []
                for src in original_sources:
                    if src.get("doc_id") in allowed_docs_enforce:
                        filtered_sources.append(src)
                    else:
                        logger.error(f"CRITICAL: Generated source from {src.get('doc_id')} not in allowed docs! Removing.")
                response["sources"] = filtered_sources
                logger.info(f"Filtered sources: {len(original_sources)} -> {len(filtered_sources)}")

            response = enforcer.enforce_evidence(response, evidences, allowed_doc_ids=allowed_docs_enforce)

            # 5. Track citations (with document filtering for follow-up questions)
            allowed_docs = allowed_docs_enforce

            # Use fixed citation map for follow-up questions
            fixed_citation_map = session.first_response_citation_map if should_use_previous_sources and session.first_response_citation_map else None

            if fixed_citation_map:
                logger.info(f"🔵 FOLLOW-UP - Using fixed citation map")
                logger.info(f"  - Fixed citation map: {fixed_citation_map}")
                logger.info(f"  - Evidences count: {len(evidences)}")
                logger.info(f"  - Allowed docs: {allowed_docs}")

                # Verify evidence count matches first response
                first_evidence_count = session.metadata.get("first_response_evidences_count", 0) if session.metadata else 0
                if len(evidences) != first_evidence_count:
                    logger.error(f"⚠️ Evidence count mismatch! First: {first_evidence_count}, Current: {len(evidences)}")

            response = citation_tracker.track_citations(response, evidences, allowed_doc_ids=allowed_docs, fixed_citation_map=fixed_citation_map)
            
            # 6. Format response (with document filtering for follow-up questions)
            allowed_docs_format = allowed_docs_enforce

            # 6.1 답변 텍스트에서 잘못된 출처 번호 제거
            if allowed_docs_format:
                # sources 개수 확인
                max_source_num = len(response.get("sources", []))
                answer = response.get("answer", "")

                # [N] 형식의 출처 번호 찾기 및 필터링
                import re
                def filter_citations(text):
                    def replace_citation(match):
                        num = int(match.group(1))
                        if num <= max_source_num:
                            return match.group(0)
                        else:
                            logger.warning(f"Removing invalid citation [{num}] (max: {max_source_num})")
                            return ""
                    return re.sub(r'\[(\d+)\]', replace_citation, text)

                response["answer"] = filter_citations(answer)
                if "details" in response:
                    response["details"] = filter_citations(response.get("details", ""))
                if "key_facts" in response:
                    response["key_facts"] = [filter_citations(fact) for fact in response.get("key_facts", [])]

            response = formatter.format_response(response, allowed_doc_ids=allowed_docs_format)
            
            # Add assistant message
            sources = response.get("sources", [])

            # 후속 답변인 경우 sources 검증
            if should_use_previous_sources:
                if not sources:
                    logger.error("⚠️ No sources found in follow-up response!")
                else:
                    logger.info(f"Follow-up response has {len(sources)} sources")
                    # Log source details for debugging
                    for idx, src in enumerate(sources[:3]):
                        logger.debug(f"Source {idx+1}: doc_id={src.get('doc_id')}, page={src.get('page')}")

            assistant_content = response.get("formatted_text", response.get("answer", ""))

            # 세션 제목 업데이트 (첫 메시지인 경우)
            title_updated = False
            new_title = None
            if len(context) == 0:  # 첫 대화인 경우
                try:
                    new_title = await get_title_generator().generate_title(
                        request.query,
                        assistant_content[:500]
                    )
                    if new_title and new_title != "새 대화":
                        await session_manager.update_session(session_id, title=new_title)
                        title_updated = True
                        logger.info(f"Session {session_id} title updated to: {new_title}")
                except Exception as e:
                    logger.error(f"Failed to generate title: {e}")

            source_doc_ids = [s.get("doc_id") for s in sources if s.get("doc_id")]
            unique_doc_ids = _deduplicate_doc_ids(source_doc_ids)

            doc_scope_metadata = _finalize_doc_scope_metadata(
                doc_scope_metadata,
                mode=doc_scope_mode,
                doc_scope_ids=doc_scope_ids,
                resolved_doc_ids=unique_doc_ids,
                requested_doc_ids=_deduplicate_doc_ids(requested_doc_ids),
                diagnostics=resolution.diagnostics,
                average_score=_average_evidence_score(evidences),
                topic_change=topic_change_detected,
                topic_reason=topic_change_reason,
                topic_suggested=_deduplicate_doc_ids(topic_change_suggested),
            )

            # 첫 답변인 경우 evidences와 citation_map 저장
            is_first_response = len([m for m in session.messages if m.role == "assistant"]) == 1
            if is_first_response and not session.first_response_evidences:
                citation_map = response.get("citation_map", {})
                logger.info("🔴 FIRST RESPONSE - Saving evidences and citation map")
                logger.info(f"  - Evidences count: {len(evidences)}")
                logger.info(f"  - Citation map: {citation_map}")
                logger.info(f"  - Sources count: {len(sources)}")

                for idx, e in enumerate(evidences[:3]):
                    logger.info(f"  - Evidence {idx}: doc_id={e.get('doc_id')}, page={e.get('page')}")

                await session_manager.update_session(
                    session_id,
                    first_response_evidences=evidences,
                    first_response_citation_map=citation_map,
                    metadata={
                        **((session.metadata or {})),
                        "first_response_evidences_count": len(evidences),
                        "first_response_citation_count": len(citation_map)
                    }
                )

            # Update session memory if summarizer is confident
            latest_context = await session_manager.get_session_context(session_id, max_messages=4)
            summary_result = get_summarizer().summarize(
                latest_context,
                previous_summary=previous_summary,
                previous_entities=session.recent_entities or []
            )

            summary_updated = False
            entities_count = len(session.recent_entities or [])
            summary_confidence = summary_result.confidence if summary_result else 0.0

            if summary_result:
                if summary_result.should_use_summary and not summary_result.used_fallback:
                    await session_manager.update_session(
                        session_id,
                        conversation_summary=summary_result.summary_text,
                        recent_entities=summary_result.entities,
                        recent_source_doc_ids=unique_doc_ids
                    )
                    summary_updated = True
                    entities_count = len(summary_result.entities)
                else:
                    logger.info(
                        "Summary not updated due to confidence gate",
                        extra={
                            "session_id": session_id,
                            "summary_confidence": summary_result.confidence,
                            "used_fallback": summary_result.used_fallback,
                        },
                    )
                    if unique_doc_ids:
                        await session_manager.update_session(
                            session_id,
                            recent_source_doc_ids=unique_doc_ids
                        )
            elif unique_doc_ids:
                await session_manager.update_session(
                    session_id,
                    recent_source_doc_ids=unique_doc_ids
                )

            # 메모리 팩트 저장 비활성화 - 출처 일관성 문제 해결을 위해
            # memory_facts = _collect_memory_facts(response)
            # if memory_facts:
            #     await session_manager.add_memory_facts(session_id, memory_facts)
            logger.debug("Memory facts collection disabled for source consistency")

            response_metadata = {
                "evidence_count": len(evidences),
                "hallucination_detected": response.get("verification", {}).get("hallucination_detected", False),
                "context_messages": len(context),
                "rewrite": {
                    "used_fallback": rewrite_result.used_fallback,
                    "search_query": rewrite_result.search_query,
                    "reasoning": rewrite_result.reasoning,
                    "sub_queries": rewrite_result.sub_queries,
                },
                "doc_scope": doc_scope_metadata,
                "memory": {
                    "summary_available": bool(previous_summary),
                    "summary_updated": summary_updated,
                    "entities_count": entities_count,
                    "summarizer_confidence": summary_confidence,
                    "source_doc_ids": unique_doc_ids,
                },
                "title_updated": title_updated,
                "new_title": new_title if title_updated else None
            }

            response_metadata["raw_answer"] = response.get("answer", "")
            response_metadata["formatted_text"] = assistant_content
            response_metadata["key_facts"] = response.get("key_facts", [])
            response_metadata["details"] = response.get("details", "")
            response_metadata["grounding"] = response.get("grounding", [])

            await session_manager.add_message(
                session_id,
                "assistant",
                assistant_content,
                sources=sources,
                metadata=response_metadata
            )

            logger.info(
                "Response scope summary",
                extra={
                    "session_id": session_id,
                    "doc_scope": doc_scope_metadata,
                },
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
                metadata=response_metadata
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

            if not request.query or not request.query.strip():
                yield json.dumps({"error": "메시지를 입력해 주세요"}) + "\n"
                return

            if not session.document_ids and not getattr(request, "skip_document_check", False):
                yield json.dumps({
                    "error": "NO_DOCUMENTS",
                    "message": "먼저 문서를 업로드해 주세요"
                }) + "\n"
                return

            # Add user message
            await session_manager.add_message(session_id, "user", request.query)

            previous_summary = session.conversation_summary or ""

            # Build context and rewrite query
            context_messages = await session_manager.get_session_context(session_id, max_messages=10)

            # 이전 답변의 출처 추적 (첫 번째 assistant 메시지 기준으로 고정)
            previous_sources: List[Dict[str, Any]] = []
            previous_doc_ids: List[str] = []
            first_assistant_found = False

            # 첫 답변의 고정된 evidences에서 문서 범위만 추출 (evidence 자체는 재사용하지 않음)
            if session.first_response_evidences:
                first_assistant_found = True
                # Extract doc_ids from stored evidences (문서 범위만 사용)
                previous_doc_ids = list(set([
                    e.get("doc_id")
                    for e in session.first_response_evidences
                    if e.get("doc_id")
                ]))
                logger.info(f"Streaming: Using doc scope from first response: docs: {previous_doc_ids} (will search for new evidences)")
            else:
                # 첫 번째 assistant 메시지의 출처를 찾아서 고정
                for message in session.messages:
                    if message.role == "assistant" and message.sources and not first_assistant_found:
                        previous_sources = message.sources
                        previous_doc_ids = [
                            src.get("doc_id")
                            for src in message.sources
                            if isinstance(src, dict) and src.get("doc_id")
                        ]
                        first_assistant_found = True
                        logger.info(f"Streaming: Using first assistant message sources: {previous_doc_ids}")
                        break

            # 첫 번째 assistant가 없으면 가장 최근 것을 사용 (폴백)
            if not first_assistant_found:
                for message in reversed(session.messages):
                    if message.role == "assistant" and message.sources:
                        previous_sources = message.sources
                        previous_doc_ids = [
                            src.get("doc_id")
                            for src in message.sources
                            if isinstance(src, dict) and src.get("doc_id")
                        ]
                        logger.info(f"Streaming: Using recent assistant message sources (fallback): {previous_doc_ids}")
                        break

            recent_for_rewrite = context_messages[-4:] if context_messages else []
            rewrite_context = RewriteContext(
                current_query=request.query,
                recent_messages=recent_for_rewrite,
                summary=previous_summary,
                entities=session.recent_entities or [],
                previous_sources=previous_sources
            )
            rewrite_result = get_query_rewriter().rewrite(rewrite_context)
            retrieval_query = request.query if rewrite_result.used_fallback else rewrite_result.search_query

            # Determine retrieval scope
            requested_doc_ids: List[str] = []
            if request.doc_ids:
                requested_doc_ids = [doc_id for doc_id in request.doc_ids if doc_id in session.document_ids]
                if not requested_doc_ids:
                    yield json.dumps({"error": "요청한 문서를 세션에서 찾을 수 없습니다"}) + "\n"
                    return

            should_use_previous_sources = bool(previous_doc_ids) and not requested_doc_ids
            doc_scope_metadata: Dict[str, Any] = {}
            allowed_docs_enforce: Optional[List[str]] = None
            doc_scope_ids: List[str] = []
            topic_change_detected = False
            topic_change_reason: Optional[str] = None
            topic_change_suggested: List[str] = []

            # Send status update
            yield json.dumps({
                "status": "문서 검색 중...",
                "metadata": {
                    "rewrite_used_fallback": rewrite_result.used_fallback
                }
            }) + "\n"

            retriever_instance = get_retriever()
            resolution = _resolve_evidences(
                query=request.query,
                retrieval_query=retrieval_query,
                retriever_instance=retriever_instance,
                requested_doc_ids=requested_doc_ids,
                session_doc_ids=session.document_ids or [],
                previous_doc_ids=previous_doc_ids,
                should_use_previous_sources=should_use_previous_sources,
            )

            if resolution.status == "no_evidence":
                message = resolution.error_message or "업로드된 문서에서 해당 정보를 찾을 수 없습니다."
                yield json.dumps({
                    "error": "no_evidence",
                    "message": message
                }) + "\n"
                await session_manager.add_message(
                    session_id,
                    "assistant",
                    message,
                    error="no_evidence",
                    metadata={"doc_scope": resolution.metadata},
                )
                return

            evidences = resolution.evidences
            doc_scope_metadata = dict(resolution.metadata or {})
            allowed_docs_enforce = resolution.allowed_doc_ids
            topic_change_detected = resolution.topic_change_detected
            topic_change_reason = resolution.topic_change_reason
            topic_change_suggested = resolution.topic_change_suggested or []
            should_use_previous_sources = resolution.allow_fixed_citations
            doc_scope_ids = resolution.doc_scope_ids
            doc_scope_mode = resolution.doc_scope_mode

            if cancel_event.is_set():
                return

            # Send status update
            yield json.dumps({
                "status": "문서 검색 완료",
                "metadata": {
                    "doc_scope": doc_scope_metadata,
                    "rewrite_used_fallback": rewrite_result.used_fallback
                }
            }) + "\n"

            # Send status update for generation
            yield json.dumps({"status": "답변 생성 중..."}) + "\n"

            # Rerank if available (후속 질문에서도 항상 reranking 수행)
            # 첫 답변 evidences 재사용 로직 제거 - 항상 새로 검색한 evidence를 rerank
            reranker_instance = get_reranker()
            if reranker_instance and (
                getattr(reranker_instance, "model", None)
                or (getattr(reranker_instance, "use_onnx", False) and hasattr(reranker_instance, "ort_session"))
            ):
                evidences = reranker_instance.rerank(
                    retrieval_query,
                    evidences,
                    top_k=config.TOPK_RERANK
                )
                logger.info(f"Streaming: Reranked {len(evidences)} evidences for query")
            else:
                evidences = evidences[:config.TOPK_RERANK]

            # Stream generation with explicit generator handle for clean aclose
            agen = get_generator().stream_with_context(
                request.query,
                evidences,
                context=context_messages,
                doc_scope=doc_scope_metadata,
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

            allowed_docs = allowed_docs_enforce

            response_payload = {
                "answer": full_response,
                "key_facts": [],
                "details": "",
                "sources": [],
            }

            response_payload = get_response_grounder().ground(response_payload, evidences)
            response_payload = postprocessor.process(response_payload, evidences)
            response_payload = enforcer.enforce_evidence(
                response_payload,
                evidences,
                allowed_doc_ids=allowed_docs
            )
            # Use fixed citation map for follow-up questions (streaming)
            fixed_citation_map = session.first_response_citation_map if should_use_previous_sources and session.first_response_citation_map else None
            response_payload = citation_tracker.track_citations(
                response_payload,
                evidences,
                allowed_doc_ids=allowed_docs,
                fixed_citation_map=fixed_citation_map
            )
            response_payload = formatter.format_response(
                response_payload,
                allowed_doc_ids=allowed_docs
            )

            assistant_content = response_payload.get("formatted_text", response_payload.get("answer", full_response))
            sources = response_payload.get("sources", [])

            source_doc_ids = [s.get("doc_id") for s in sources if s.get("doc_id")]
            unique_doc_ids: List[str] = []
            for doc_id in source_doc_ids:
                if doc_id and doc_id not in unique_doc_ids:
                    unique_doc_ids.append(doc_id)

            doc_scope_metadata = _finalize_doc_scope_metadata(
                doc_scope_metadata,
                mode=doc_scope_mode,
                doc_scope_ids=doc_scope_ids,
                resolved_doc_ids=unique_doc_ids,
                requested_doc_ids=_deduplicate_doc_ids(requested_doc_ids),
                diagnostics=resolution.diagnostics,
                average_score=_average_evidence_score(evidences),
                topic_change=topic_change_detected,
                topic_reason=topic_change_reason,
                topic_suggested=_deduplicate_doc_ids(topic_change_suggested),
            )

            # 첫 답변인 경우 evidences와 citation_map 저장 (스트리밍)
            is_first_response = len([m for m in session.messages if m.role == "assistant"]) == 1
            if is_first_response and not session.first_response_evidences:
                citation_map = response_payload.get("citation_map", {})
                logger.info(f"Streaming: Saving first response evidences: {len(evidences)} items, citation_map: {citation_map}")
                await session_manager.update_session(
                    session_id,
                    first_response_evidences=evidences,
                    first_response_citation_map=citation_map,
                    metadata={
                        **((session.metadata or {})),
                        "first_response_evidences_count": len(evidences),
                        "first_response_citation_count": len(citation_map)
                    }
                )

            summary_updated = False
            entities_count = len(session.recent_entities or [])
            summary_confidence = 0.0

            try:
                latest_context = await session_manager.get_session_context(session_id, max_messages=4)
                summary_result = get_summarizer().summarize(
                    latest_context,
                    previous_summary=previous_summary,
                    previous_entities=session.recent_entities or []
                )
                summary_confidence = summary_result.confidence if summary_result else 0.0
                if summary_result and summary_result.should_use_summary and not summary_result.used_fallback:
                    await session_manager.update_session(
                        session_id,
                        conversation_summary=summary_result.summary_text,
                        recent_entities=summary_result.entities,
                        recent_source_doc_ids=unique_doc_ids
                    )
                    summary_updated = True
                    entities_count = len(summary_result.entities)
                elif summary_result:
                    logger.info(
                        "Streaming summary gate skipped",
                        extra={
                            "session_id": session_id,
                            "confidence": summary_result.confidence,
                            "used_fallback": summary_result.used_fallback,
                        },
                    )
                    if unique_doc_ids:
                        await session_manager.update_session(
                            session_id,
                            recent_source_doc_ids=unique_doc_ids
                        )
                elif unique_doc_ids:
                    await session_manager.update_session(
                        session_id,
                        recent_source_doc_ids=unique_doc_ids
                    )
            except Exception as e:
                logger.error(f"Failed to update summary in stream: {e}")

            response_metadata = {
                "evidence_count": len(evidences),
                "hallucination_detected": response_payload.get("verification", {}).get("hallucination_detected", False),
                "context_messages": len(context_messages),
                "rewrite": {
                    "used_fallback": rewrite_result.used_fallback,
                    "search_query": rewrite_result.search_query,
                    "reasoning": rewrite_result.reasoning,
                    "sub_queries": rewrite_result.sub_queries,
                },
                "doc_scope": doc_scope_metadata,
                "memory": {
                    "summary_available": bool(previous_summary),
                    "summary_updated": summary_updated,
                    "entities_count": entities_count,
                    "summarizer_confidence": summary_confidence,
                    "source_doc_ids": unique_doc_ids,
                },
                "streaming": True,
            }

            response_metadata["raw_answer"] = response_payload.get("answer", "")
            response_metadata["formatted_text"] = assistant_content
            response_metadata["key_facts"] = response_payload.get("key_facts", [])
            response_metadata["details"] = response_payload.get("details", "")
            response_metadata["grounding"] = response_payload.get("grounding", [])

            await session_manager.add_message(
                session_id,
                "assistant",
                assistant_content,
                sources=sources,
                metadata=response_metadata
            )

            # 메모리 팩트 저장 비활성화 - 출처 일관성 문제 해결을 위해
            # memory_facts = _collect_memory_facts(response_payload)
            # if memory_facts:
            #     await session_manager.add_memory_facts(session_id, memory_facts)
            logger.debug("Streaming: Memory facts collection disabled for source consistency")

            # Send final data with sources
            yield json.dumps({
                "complete": True,
                "answer": assistant_content,
                "sources": sources,
                "metadata": response_metadata,
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
