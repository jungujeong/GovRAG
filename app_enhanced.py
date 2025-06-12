import os
import time
import streamlit as st
from pathlib import Path
import logging
from threading import Thread, Lock, Event
import queue
import uuid
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import warnings

# PyTorch와 Streamlit 간 호환성 문제로 인한 경고 억제
warnings.filterwarnings("ignore", message=".*torch.*classes.*")
warnings.filterwarnings("ignore", message=".*no running event loop.*")
warnings.filterwarnings("ignore", message=".*ScriptRunContext.*")

# 환경 변수로도 PyTorch 경고 억제
os.environ['PYTHONWARNINGS'] = 'ignore'
os.environ['TOKENIZERS_PARALLELISM'] = 'false'  # transformers 라이브러리 경고 억제

# 특정 라이브러리 로깅 레벨 조정
import logging
logging.getLogger('torch').setLevel(logging.ERROR)
logging.getLogger('streamlit').setLevel(logging.ERROR)
logging.getLogger('watchdog').setLevel(logging.ERROR)

# 개선된 컴포넌트 임포트
from utils import (
    EnhancedDocumentProcessor, 
    EnhancedVectorStore, 
    EnhancedRAGChain
)
from config import DOCUMENTS_PATH, logger, OLLAMA_MODEL, set_session_context

# 전역 변수들
processing_queue = queue.Queue()
result_queue = queue.Queue()
processing_lock = Lock()
processing_done_flag = Event()
processing_done_flag.set()

# 세션 관리
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    user_ip = os.environ.get('REMOTE_ADDR', None)
    username = os.environ.get('REMOTE_USER', None)
    user_id = username or user_ip or f"user-{st.session_state.session_id[:8]}"
    st.session_state.user_id = user_id
    set_session_context(st.session_state.session_id, st.session_state.user_id)
    logger.info(f"새 사용자 세션 시작: {st.session_state.user_id}")

# Streamlit 설정
st.set_page_config(
    page_title="RAG 문서 기반 챗봇",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 세션 상태 초기화
session_defaults = {
    "messages": [],
    "processing_done": True,
    "processed_files": set(),
    "processing_files": set(),
    "processing_errors": {},
    "files_to_process": [],
    "processing_complete": False,
    "check_processing": False,
    "last_processing_time": time.time(),
    "uploader_key": "file_uploader_1",
    "thread_executor": None,
    "enhanced_mode": True,
    "document_summaries": {},  # 문서 요약 캐시
    "selected_document": None,  # 선택된 문서
    "show_document_preview": False,  # 문서 미리보기 표시 여부
    "debug_mode": False,  # 디버깅 모드
    "is_generating_response": False,  # 답변 생성 중 여부
    "debug_text_display": None,  # 디버그 텍스트 표시
    "debug_text_type": None,  # 디버그 텍스트 타입
    "debug_text_title": None  # 디버그 텍스트 제목
}

for key, default_value in session_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = default_value

# 컴포넌트 초기화
@st.cache_resource
def initialize_components():
    """RAG 컴포넌트 초기화"""
    if 'session_id' in st.session_state and 'user_id' in st.session_state:
        set_session_context(st.session_state.session_id, st.session_state.user_id)
    
    document_processor = EnhancedDocumentProcessor()
    vector_store = EnhancedVectorStore()
    rag_chain = EnhancedRAGChain(vector_store=vector_store)
    
    logger.info("RAG 컴포넌트 초기화 완료")
    return document_processor, vector_store, rag_chain

# 전역 컴포넌트
document_processor, vector_store, rag_chain = initialize_components()

# 앱 시작시 BM25 동기화 상태 확인 및 자동 재구성
def check_and_fix_bm25_sync():
    """앱 시작 시 BM25 동기화 상태 확인 및 자동 재구성"""
    try:
        db_info = vector_store.get_collection_info()
        chroma_docs = db_info.get('document_count', 0)
        bm25_docs = db_info.get('bm25_documents', 0)
        
        if chroma_docs > 0 and bm25_docs == 0:
            logger.warning(f"BM25 인덱스 동기화 필요: ChromaDB({chroma_docs}) vs BM25({bm25_docs})")
            vector_store._rebuild_indexes_from_chromadb()
            logger.info("앱 시작 시 BM25 인덱스 자동 재구성 완료")
            return True
    except Exception as e:
        logger.error(f"BM25 동기화 확인 실패: {e}")
    return False

# BM25 동기화 확인은 한 번만 실행
if 'bm25_sync_checked' not in st.session_state:
    st.session_state.bm25_sync_checked = True
    if check_and_fix_bm25_sync():
        logger.info("BM25 인덱스가 자동으로 재구성되었습니다.")

# CSS 스타일링 - 깔끔하고 직관적으로 개선
st.markdown(
    """
    <style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    
    /* 메인 헤더 */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    .main-header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: 700;
    }
    
    .main-header p {
        margin: 0.5rem 0 0 0;
        font-size: 1.1rem;
        opacity: 0.9;
    }
    
    /* 채팅 메시지 */
    .chat-message {
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 1rem;
        display: flex;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        border: 1px solid #e8e8e8;
    }
    
    .chat-message.user {
        background: linear-gradient(135deg, #f8f9ff 0%, #e8f0ff 100%);
        color: #2c3e50;
        border-left: 4px solid #667eea;
    }
    
    .chat-message.assistant {
        background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%);
        color: #2c3e50;
        border-left: 4px solid #28a745;
    }
    
    .chat-message .message {
        flex-grow: 1;
        color: #2c3e50;
    }
    
    /* 통계 컨테이너 */
    .stats-container {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e0e6ed;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        margin-bottom: 1rem;
    }
    
    .stats-container h4 {
        color: #2c3e50 !important;
        margin-bottom: 1rem !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .stats-container p {
        color: #495057 !important;
        margin-bottom: 0.5rem !important;
        font-size: 0.95rem !important;
        line-height: 1.4;
    }
    
    .stats-container strong {
        color: #2c3e50 !important;
        font-weight: 600 !important;
    }
    
    /* 성능 배지 */
    .performance-badge {
        background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
        color: white;
        padding: 0.4rem 1rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
        display: inline-block;
        margin: 0.3rem 0;
        box-shadow: 0 2px 4px rgba(40, 167, 69, 0.3);
    }
    
    /* 파일 목록 컨테이너 */
    .file-list-container {
        background: #ffffff;
        border: 1px solid #dee2e6;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
    }
    
    .file-list-container h4 {
        color: #2c3e50 !important;
        margin-bottom: 1rem !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    /* 파일 아이템 */
    .file-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1.2rem;
        border-bottom: 1px solid #f1f3f4;
        border-radius: 10px;
        margin-bottom: 0.8rem;
        background: linear-gradient(135deg, #fafbfc 0%, #f8f9fa 100%);
        transition: all 0.3s ease;
        min-height: 80px;
        border: 1px solid #e9ecef;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }
    
    .file-item:hover {
        background: linear-gradient(135deg, #f0f2f5 0%, #e8eaf6 100%);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        border-color: #667eea;
    }
    
    .file-item:last-child {
        border-bottom: none;
        margin-bottom: 0;
    }
    
    .file-name {
        flex-grow: 1;
        color: #2c3e50 !important;
        font-size: 0.95rem !important;
        line-height: 1.4;
        padding-right: 1rem;
    }
    
    .file-name strong {
        color: #495057 !important;
        font-weight: 600 !important;
        font-size: 1rem !important;
    }
    
    .file-name small {
        color: #6c757d !important;
        font-size: 0.85rem !important;
        display: block;
        margin-top: 0.3rem;
    }
    
    .file-actions {
        display: flex;
        gap: 0.5rem;
        align-items: center;
        flex-wrap: wrap;
    }
    
    /* 상태 표시 */
    .status-pending { color: #6c757d; }
    .status-processing { color: #fd7e14; }
    .status-complete { color: #28a745; }
    .status-overwrite { color: #dc3545; }
    
    /* 버튼 스타일 개선 */
    .stButton > button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
    }
    
    /* 진행률 바 */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
    }
    
    /* 사이드바 스타일 */
    .css-1d391kg {
        background-color: #f8f9fa;
    }
    
    /* 입력 필드 */
    .stTextInput > div > div > input {
        border-radius: 8px;
        border: 1px solid #dee2e6;
    }
    
    /* 파일 업로더 */
    .stFileUploader > div {
        border-radius: 8px;
        border: 2px dashed #dee2e6;
        background: #fafbfc;
    }
    
    /* 문서 미리보기 컨테이너 */
    .document-preview {
        background: linear-gradient(135deg, #f8f9ff 0%, #e8f0ff 100%);
        border: 1px solid #d1ecf1;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 8px rgba(0, 123, 255, 0.1);
    }
    
    .document-preview h4 {
        color: #2c3e50 !important;
        margin-bottom: 1rem !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .document-preview .summary-content {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #007bff;
        color: #2c3e50;
        line-height: 1.6;
        font-size: 0.95rem;
    }
    
    /* 디버그 컨테이너 */
    .debug-container {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        padding: 1rem;
        margin: 0.5rem 0;
        font-family: 'Courier New', monospace;
        font-size: 0.85rem;
        max-height: 300px;
        overflow-y: auto;
    }
    
    .debug-container pre {
        margin: 0;
        white-space: pre-wrap;
        word-wrap: break-word;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 헤더
st.markdown(
    """
    <div class="main-header">
        <h1>📚 RAG 문서 기반 챗봇</h1>
        <p>하이브리드 검색 · 다단계 추론 · 답변 검증</p>
    </div>
    """,
    unsafe_allow_html=True
)

def add_document_to_vectorstore_enhanced(file_path, file_name):
    """문서 추가 함수 (중복 문서 덮어쓰기 지원)"""
    try:
        logger.info(f"문서 처리 시작: {file_name}")
        
        # 1. 기존 문서 확인 및 삭제 (중복 처리)
        deleted_existing = False
        try:
            existing_docs = vector_store.get_document_by_metadata({"source": file_name})
            if existing_docs:
                logger.info(f"기존 문서 발견: {file_name}, 삭제 후 재추가")
                # ChromaDB에서 직접 삭제
                collection = vector_store.vector_store._collection
                delete_results = collection.get(where={"source": file_name})
                if delete_results.get('ids'):
                    collection.delete(ids=delete_results['ids'])
                    deleted_existing = True
                    logger.info(f"기존 문서 삭제 완료: {len(delete_results['ids'])}개 청크")
        except Exception as e:
            logger.warning(f"기존 문서 삭제 중 오류 (계속 진행): {e}")
        
        # 2. 문서 유효성 검사
        is_valid, message = document_processor.validate_document(file_path)
        if not is_valid:
            logger.error(f"문서 유효성 검사 실패: {message}")
            return False, message
        
        # 3. 문서 처리 (청크 생성)
        chunks, summary_info = document_processor.process_document(file_path)
        
        if not chunks:
            error_msg = "문서에서 유효한 내용을 추출할 수 없습니다."
            logger.error(error_msg)
            return False, error_msg
        
        # 4. 벡터 스토어에 추가
        doc_ids = vector_store.add_documents(chunks)
        
        # 5. 중복 문서를 삭제했다면 BM25 인덱스 전체 재구성
        if deleted_existing:
            try:
                vector_store._rebuild_indexes_from_chromadb()
                logger.info("기존 문서 삭제로 인한 BM25 인덱스 재구성 완료")
            except Exception as e:
                logger.warning(f"BM25 인덱스 재구성 실패 (검색 성능에 영향 가능): {e}")
        
        logger.info(f"문서 추가 성공: {file_name}, 청크 수: {len(chunks)}")
        return True, f"성공적으로 처리됨 ({len(chunks)}개 청크)"
        
    except Exception as e:
        error_msg = f"문서 처리 중 오류: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def process_single_document_enhanced(file_item, session_id, user_id):
    """단일 파일 처리"""
    file_path, file_name = file_item
    set_session_context(session_id, user_id)
    
    try:
        logger.info(f"'{file_name}' 처리 시작")
        success, message = add_document_to_vectorstore_enhanced(file_path, file_name)
        
        # 결과 큐에 추가
        result_queue.put({
            'file_name': file_name,
            'success': success,
            'message': message,
            'timestamp': datetime.now()
        })
        
        return success, message
        
    except Exception as e:
        error_msg = f"파일 처리 실패: {str(e)}"
        logger.error(error_msg)
        result_queue.put({
            'file_name': file_name,
            'success': False,
            'message': error_msg,
            'timestamp': datetime.now()
        })
        return False, error_msg

def process_documents_thread_enhanced(session_id, user_id, files_to_process_list):
    """문서 처리 스레드 (스레드 안전한 버전)"""
    try:
        set_session_context(session_id, user_id)
        
        with processing_lock:
            if not processing_done_flag.is_set():
                logger.warning("이미 처리가 진행 중입니다")
                return
            
            processing_done_flag.clear()
        
        # 매개변수로 받은 파일 목록 사용 (세션 상태에 직접 접근하지 않음)
        logger.info(f"{len(files_to_process_list)}개 파일 처리 시작")
        
        # ThreadPoolExecutor를 사용한 병렬 처리
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for file_item in files_to_process_list:
                future = executor.submit(
                    process_single_document_enhanced, 
                    file_item, 
                    session_id, 
                    user_id
                )
                futures.append(future)
            
            # 모든 작업 완료 대기
            for future in futures:
                try:
                    future.result(timeout=300)  # 5분 타임아웃
                except Exception as e:
                    logger.error(f"문서 처리 중 예외 발생: {e}")
        
        logger.info("모든 문서 처리 완료")
        
    except Exception as e:
        logger.error(f"문서 처리 스레드 오류: {e}")
    finally:
        processing_done_flag.set()

def get_document_summary(doc_name: str) -> str:
    """문서 요약 생성 (캐시 적용)"""
    try:
        # 캐시에서 확인
        if doc_name in st.session_state.document_summaries:
            return st.session_state.document_summaries[doc_name]
        
        # ChromaDB에서 해당 문서의 모든 청크 가져오기
        collection = vector_store.vector_store._collection
        results = collection.get(where={"source": doc_name})
        
        if not results.get('documents'):
            return "문서 내용을 찾을 수 없습니다."
        
        # 모든 청크 내용을 합쳐서 전체 텍스트 구성
        full_text = "\n\n".join(results['documents'])
        
        # 너무 긴 경우 앞부분만 사용 (요약용)
        if len(full_text) > 5000:
            full_text = full_text[:5000] + "..."
        
        # RAG 체인을 통한 요약 생성
        summary = rag_chain.summarize_document(full_text)
        
        # 캐시에 저장
        st.session_state.document_summaries[doc_name] = summary
        
        return summary
        
    except Exception as e:
        logger.error(f"문서 요약 생성 실패: {e}")
        return f"요약 생성 중 오류가 발생했습니다: {str(e)}"

def get_document_full_text(doc_name: str) -> str:
    """문서 전체 텍스트 가져오기 (디버깅용)"""
    try:
        collection = vector_store.vector_store._collection
        results = collection.get(where={"source": doc_name})
        
        if not results.get('documents'):
            return "문서 내용을 찾을 수 없습니다."
        
        # 모든 청크를 번호와 함께 표시
        full_text_parts = []
        for i, chunk in enumerate(results['documents'], 1):
            full_text_parts.append(f"=== 청크 {i} ===\n{chunk}\n")
        
        return "\n".join(full_text_parts)
        
    except Exception as e:
        logger.error(f"전체 텍스트 조회 실패: {e}")
        return f"텍스트 조회 중 오류가 발생했습니다: {str(e)}"

# 사이드바 설정
with st.sidebar:
    st.header("📁 문서 업로드")
    
    # 벡터 DB 정보 표시
    try:
        db_info = vector_store.get_collection_info()
        chroma_docs = db_info.get('document_count', 0)
        bm25_docs = db_info.get('bm25_documents', 0)
        
        # BM25 문서 수가 ChromaDB 문서 수와 다르면 경고 표시
        sync_status = "✅ 동기화됨" if chroma_docs == bm25_docs else "⚠️ 동기화 필요"
        sync_color = "#28a745" if chroma_docs == bm25_docs else "#ffc107"
        
        st.markdown(
            f"""
            <div class="stats-container">
                <h4>📊 데이터베이스 상태</h4>
                <p><strong>문서 수:</strong> {chroma_docs}</p>
                <p><strong>BM25 문서:</strong> {bm25_docs}</p>
                <p><strong>컬렉션:</strong> {db_info.get('collection_name', 'N/A')}</p>
                <p style="color: {sync_color}; font-weight: bold;"><strong>상태:</strong> {sync_status}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
        
        # BM25 인덱스 재구성 버튼 (동기화가 안된 경우)
        if chroma_docs != bm25_docs and chroma_docs > 0:
            if st.button("🔄 BM25 인덱스 재구성", help="서버 재시작 후 검색이 안될 때 사용"):
                with st.spinner("BM25 인덱스 재구성 중..."):
                    try:
                        vector_store._rebuild_indexes_from_chromadb()
                        st.success(f"BM25 인덱스 재구성 완료! ({chroma_docs}개 문서)")
                        st.rerun()  # 페이지 새로고침
                    except Exception as e:
                        st.error(f"BM25 인덱스 재구성 실패: {e}")
                        logger.error(f"Manual BM25 rebuild failed: {e}")
        
    except Exception as e:
        st.warning(f"DB 상태 조회 실패: {e}")
    
    # 성능 통계 표시
    try:
        perf_stats = rag_chain.get_performance_stats()
        if perf_stats.get('total_queries', 0) > 0:
            st.markdown(
                f"""
                <div class="stats-container">
                    <h4>⚡ 성능 통계</h4>
                    <p><strong>총 질의:</strong> {perf_stats.get('total_queries', 0)}</p>
                    <p><strong>평균 응답시간:</strong> {perf_stats.get('avg_response_time', 0):.2f}초</p>
                    <p><strong>검증률:</strong> {perf_stats.get('verification_rate', 0):.1%}</p>
                    <span class="performance-badge">고성능 시스템</span>
                </div>
                """,
                unsafe_allow_html=True
            )
    except Exception as e:
        st.warning(f"성능 통계 조회 실패: {e}")
    
    # 파일 업로드
    uploaded_files = st.file_uploader(
        "📁 PDF, HWP, TXT 파일을 업로드하세요",
        type=['pdf', 'hwp', 'txt', 'md'],
        accept_multiple_files=True,
        key=st.session_state.uploader_key,
        help="여러 파일을 동시에 선택할 수 있습니다. 같은 이름의 파일은 자동으로 덮어쓰기됩니다."
    )
    
    if uploaded_files:
        st.subheader("📤 파일 업로드")
        
        # 업로드된 파일 상태 표시
        st.markdown("**📤 업로드된 파일:**")
        for uploaded_file in uploaded_files:
            # 파일 상태 확인
            is_processed = uploaded_file.name in st.session_state.processed_files
            is_processing = uploaded_file.name in st.session_state.processing_files
            
            # 기존 문서인지 확인
            try:
                collection = vector_store.vector_store._collection
                existing = collection.get(where={"source": uploaded_file.name})
                is_existing = bool(existing.get('ids'))
            except:
                is_existing = False
            
            # 상태 아이콘 및 텍스트 결정
            if is_processed:
                status_icon = "✅"
                status_text = "처리 완료"
                status_class = "status-complete"
            elif is_processing:
                status_icon = "🔄"
                status_text = "처리 중"
                status_class = "status-processing"
            elif is_existing:
                status_icon = "🔄"
                status_text = "덮어쓰기 예정"
                status_class = "status-overwrite"
            else:
                status_icon = "📄"
                status_text = "대기 중"
                status_class = "status-pending"
            
            # 파일 크기 표시
            file_size = len(uploaded_file.getvalue()) / 1024  # KB
            size_text = f"{file_size:.1f}KB" if file_size < 1024 else f"{file_size/1024:.1f}MB"
            
            st.markdown(
                f"""
                <div style="display: flex; align-items: center; padding: 0.5rem; margin: 0.3rem 0; 
                           background: #f8f9fa; border-radius: 8px; border-left: 3px solid #dee2e6;">
                    <span style="font-size: 1.2rem; margin-right: 0.5rem;">{status_icon}</span>
                    <div style="flex-grow: 1;">
                        <div style="font-weight: 600; color: #2c3e50;">{uploaded_file.name}</div>
                        <div style="font-size: 0.8rem; color: #6c757d;">{size_text} • <span class="{status_class}">{status_text}</span></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
        
        files_to_process = []
        for uploaded_file in uploaded_files:
            # 파일 저장 (항상 덮어쓰기)
            file_path = os.path.join(DOCUMENTS_PATH, uploaded_file.name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            files_to_process.append((file_path, uploaded_file.name))
        
        if files_to_process:
            st.session_state.files_to_process = files_to_process
            
            col1, col2 = st.columns([3, 1])
            with col1:
                process_button = st.button(
                    f"🚀 {len(files_to_process)}개 문서 처리하기", 
                    type="primary", 
                    use_container_width=True,
                    disabled=not st.session_state.processing_done
                )
            with col2:
                if not st.session_state.processing_done:
                    st.markdown("🔄 **처리 중**")
            
            if process_button:
                st.session_state.processing_done = False
                st.session_state.check_processing = True
                
                # 백그라운드에서 처리 시작 (파일 목록을 매개변수로 전달)
                files_copy = list(st.session_state.files_to_process)
                thread = Thread(
                    target=process_documents_thread_enhanced,
                    args=(st.session_state.session_id, st.session_state.user_id, files_copy),
                    daemon=True
                )
                thread.start()
                st.rerun()
    
    # 처리 진행 상황 확인
    if st.session_state.check_processing and not st.session_state.processing_done:
        # 진행률 표시
        total_files = len(st.session_state.files_to_process) if hasattr(st.session_state, 'files_to_process') else 1
        processed_count = len(st.session_state.processed_files)
        error_count = len(st.session_state.processing_errors)
        
        progress = min((processed_count + error_count) / total_files, 1.0) if total_files > 0 else 0
        
        # 진행률 바 표시
        progress_bar = st.progress(progress)
        status_text = st.empty()
        
        if progress < 1.0:
            status_text.info(f"🔄 처리 중: {processed_count + error_count}/{total_files} 완료")
        
        with st.spinner("문서 처리 중..."):
            time.sleep(1)
            
            # 결과 확인
            results_processed = 0
            try:
                while not result_queue.empty():
                    result = result_queue.get()
                    file_name = result['file_name']
                    
                    if result['success']:
                        st.session_state.processed_files.add(file_name)
                        st.success(f"✅ {file_name}: {result['message']}")
                    else:
                        st.session_state.processing_errors[file_name] = result['message']
                        st.error(f"❌ {file_name}: {result['message']}")
                    
                    results_processed += 1
            except Exception as e:
                logger.warning(f"결과 처리 중 오류 (무시됨): {e}")
            
            # 처리 완료 확인
            if processing_done_flag.is_set():
                try:
                    st.session_state.processing_done = True
                    st.session_state.check_processing = False
                    st.session_state.files_to_process = []
                    
                    # 업로더 키 변경 (UI 갱신)
                    current_key = st.session_state.uploader_key
                    new_key = f"file_uploader_{int(current_key.split('_')[-1]) + 1}"
                    st.session_state.uploader_key = new_key
                    
                    # 최종 진행률 업데이트
                    progress_bar.progress(1.0)
                    status_text.success(f"🎉 모든 문서 처리 완료! (성공: {len(st.session_state.processed_files)}, 실패: {len(st.session_state.processing_errors)})")
                    
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    logger.warning(f"처리 완료 상태 업데이트 중 오류: {e}")
                    st.rerun()
            else:
                st.rerun()
    
    # 업로드된 파일 목록 표시
    st.subheader("📄 저장된 문서")
    try:
        # ChromaDB에서 모든 문서의 메타데이터 가져오기
        collection = vector_store.vector_store._collection
        all_results = collection.get()
        
        # 문서별로 그룹화 (source 기준)
        documents = {}
        if all_results.get('metadatas'):
            for metadata in all_results['metadatas']:
                source = metadata.get('source', 'Unknown')
                if source not in documents:
                    documents[source] = {
                        'chunk_count': 0,
                        'file_type': metadata.get('file_type', 'unknown'),
                        'added_at': metadata.get('added_at', 'Unknown')
                    }
                documents[source]['chunk_count'] += 1
        
        if documents:
            st.markdown(
                f"""
                <div class="file-list-container">
                    <h4>📊 총 {len(documents)}개 문서 저장됨</h4>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # 각 문서별로 표시 및 액션 버튼들
            for doc_name, doc_info in documents.items():
                # 파일 확장자에 따른 아이콘
                if doc_name.lower().endswith('.pdf'):
                    file_icon = "📄"
                elif doc_name.lower().endswith('.hwp'):
                    file_icon = "📝"
                elif doc_name.lower().endswith(('.txt', '.md')):
                    file_icon = "📃"
                else:
                    file_icon = "📄"
                
# 파일 아이템을 더 간단하게 표시
                
                # 클릭 가능한 파일명과 삭제 버튼
                col1, col2 = st.columns([5, 1])
                
                with col1:
                    # 클릭 가능한 파일명 버튼
                    if st.button(f"{file_icon} {doc_name}", key=f"select_{doc_name}", help=f"{doc_name} 클릭하여 요약 보기", use_container_width=True):
                        # 문서 요약을 채팅 상단에 표시
                        st.session_state.selected_document = doc_name
                        st.session_state.show_document_preview = True
                        st.rerun()
                    
                    # 파일 정보 표시
                    st.caption(f"청크: {doc_info['chunk_count']}개 | 타입: {doc_info['file_type'].upper()}")
                
                with col2:
                    if st.button("🗑️", key=f"delete_{doc_name}", help=f"{doc_name} 삭제", use_container_width=True):
                        try:
                            # ChromaDB에서 해당 문서의 모든 청크 삭제
                            delete_results = collection.get(where={"source": doc_name})
                            if delete_results.get('ids'):
                                collection.delete(ids=delete_results['ids'])
                                # 캐시에서도 제거
                                if doc_name in st.session_state.document_summaries:
                                    del st.session_state.document_summaries[doc_name]
                                st.success("✅")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.warning(f"⚠️ {doc_name}을 찾을 수 없습니다")
                        except Exception as e:
                            st.error(f"❌ 삭제 실패: {e}")
                
                # 각 문서 사이에 작은 간격 추가
                st.markdown("")
        else:
            st.markdown(
                """
                <div style="text-align: center; padding: 2rem; color: #6c757d;">
                    <div style="font-size: 3rem; margin-bottom: 1rem;">📭</div>
                    <h4>저장된 문서가 없습니다</h4>
                    <p>위에서 문서를 업로드해주세요.</p>
                </div>
                """,
                unsafe_allow_html=True
            )
    
    except Exception as e:
        st.error(f"문서 목록 조회 실패: {e}")
    
    # 디버깅 도구 섹션
    st.divider()
    st.subheader("🔧 디버깅 도구")
    
    # 디버그 모드 토글
    debug_mode = st.checkbox("🔍 디버그 모드 활성화", value=st.session_state.debug_mode, help="개발자용 고급 도구 표시")
    st.session_state.debug_mode = debug_mode
    
    if debug_mode:
        st.markdown("**🛠️ 개발자 도구**")
        
        # 벡터 스토어 상세 정보
        with st.expander("📊 벡터 스토어 상세 정보"):
            try:
                db_info = vector_store.get_collection_info()
                if db_info:
                    st.json(db_info)
                else:
                    st.info("📊 벡터 스토어 정보를 가져올 수 없습니다.")
            except Exception as e:
                st.error(f"정보 조회 실패: {e}")
        
        # 성능 통계 상세
        with st.expander("⚡ 성능 통계 상세"):
            try:
                perf_stats = rag_chain.get_performance_stats()
                if perf_stats and any(perf_stats.values()):
                    st.json(perf_stats)
                else:
                    st.info("📊 아직 질의가 수행되지 않아 통계 데이터가 없습니다.")
            except Exception as e:
                st.error(f"성능 통계 조회 실패: {e}")
        
        # 문서 처리 테스트
        with st.expander("🧪 문서 처리 테스트"):
            # ChromaDB에서 실제 문서 목록 가져오기
            try:
                collection = vector_store.vector_store._collection
                all_results = collection.get()
                available_docs = []
                if all_results.get('metadatas'):
                    sources = set()
                    for metadata in all_results['metadatas']:
                        source = metadata.get('source', '')
                        if source and source not in sources:
                            sources.add(source)
                            available_docs.append(source)
                
                test_doc = st.selectbox(
                    "테스트할 문서 선택:",
                    options=available_docs if available_docs else ["문서 없음"],
                    help="선택한 문서로 다양한 테스트 수행"
                )
            except Exception as e:
                st.error(f"문서 목록 조회 실패: {e}")
                test_doc = "문서 없음"
            
            if test_doc and test_doc != "문서 없음":
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📝 요약 재생성", help="문서 요약을 다시 생성합니다"):
                        if test_doc in st.session_state.document_summaries:
                            del st.session_state.document_summaries[test_doc]
                        new_summary = get_document_summary(test_doc)
                        st.success("✅ 요약 재생성 완료")
                        st.markdown("**📝 새로운 요약**")
                        st.markdown(
                            f"""
                            <div style="background: #f8f9fa; padding: 1rem; border-radius: 8px; 
                                       border: 1px solid #dee2e6; margin: 0.5rem 0;">
                            {new_summary}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                
                with col2:
                    if st.button("🔍 청크 분석", help="문서의 청크 구조를 분석합니다"):
                        try:
                            collection = vector_store.vector_store._collection
                            results = collection.get(where={"source": test_doc})
                            
                            st.write(f"**총 청크 수:** {len(results.get('documents', []))}")
                            if results.get('documents'):
                                chunk_lengths = [len(doc) for doc in results['documents']]
                                st.write(f"**평균 청크 길이:** {sum(chunk_lengths)/len(chunk_lengths):.0f}자")
                                st.write(f"**최소/최대 청크 길이:** {min(chunk_lengths)}/{max(chunk_lengths)}자")
                        except Exception as e:
                            st.error(f"청크 분석 실패: {e}")
        
        # PDF 테이블 처리 도구 (table_utils.py 연동)
        with st.expander("📋 PDF 테이블 처리 도구"):
            st.markdown("**table_utils.py를 활용한 PDF 텍스트 분석**")
            
            # ChromaDB에서 PDF 파일만 필터링
            try:
                collection = vector_store.vector_store._collection
                all_results = collection.get()
                pdf_docs = []
                if all_results.get('metadatas'):
                    sources = set()
                    for metadata in all_results['metadatas']:
                        source = metadata.get('source', '')
                        if source and source not in sources and source.lower().endswith('.pdf'):
                            sources.add(source)
                            pdf_docs.append(source)
            except Exception as e:
                st.error(f"PDF 문서 목록 조회 실패: {e}")
                pdf_docs = []
            
            if pdf_docs:
                selected_pdf = st.selectbox("PDF 문서 선택:", pdf_docs, help="분석할 PDF 문서를 선택하세요")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button("📄 원본 텍스트", help="PDF에서 추출한 원본 텍스트를 표시합니다"):
                        raw_text = get_document_full_text(selected_pdf)
                        st.session_state.debug_text_display = raw_text
                        st.session_state.debug_text_type = "raw"
                        st.session_state.debug_text_title = f"📄 {selected_pdf} - 원본 텍스트"
                        st.success("✅ 원본 텍스트가 메인 화면에 표시됩니다")
                        st.rerun()
                
                with col2:
                    if st.button("🔍 구조화 미리보기", help="table_utils.py 로직으로 구조화된 텍스트를 미리봅니다"):
                        try:
                            # table_utils.py의 함수들을 활용한 텍스트 구조화
                            import table_utils
                            
                            # 문서 텍스트 가져오기
                            collection = vector_store.vector_store._collection
                            results = collection.get(where={"source": selected_pdf})
                            
                            if results.get('documents'):
                                full_text = "\n\n".join(results['documents'])
                                
                                # 간단한 구조화 예시 (실제 table_utils 로직에 맞게 수정 필요)
                                lines = full_text.split('\n')
                                structured_lines = []
                                
                                for line in lines:
                                    if line.strip():
                                        # 날짜 패턴 확인
                                        if table_utils.DATE_RE.match(line.strip()):
                                            structured_lines.append(f"📅 {line.strip()}")
                                        # 불릿 포인트 확인
                                        elif any(bullet in line for bullet in table_utils.ALL_BULLETS):
                                            structured_lines.append(f"• {line.strip()}")
                                        else:
                                            structured_lines.append(line.strip())
                                
                                structured_text = "\n".join(structured_lines)
                                st.session_state.debug_text_display = structured_text
                                st.session_state.debug_text_type = "structured"
                                st.session_state.debug_text_title = f"🔍 {selected_pdf} - 구조화된 텍스트"
                                st.success("✅ 구조화된 텍스트가 메인 화면에 표시됩니다")
                                st.rerun()
                            else:
                                st.warning("문서 텍스트를 찾을 수 없습니다.")
                                
                        except Exception as e:
                            st.error(f"구조화 처리 실패: {e}")
                
                with col3:
                    if st.button("📊 텍스트 통계", help="텍스트의 상세 통계를 보여줍니다"):
                        try:
                            collection = vector_store.vector_store._collection
                            results = collection.get(where={"source": selected_pdf})
                            
                            if results.get('documents'):
                                full_text = "\n\n".join(results['documents'])
                                
                                # 기본 통계
                                char_count = len(full_text)
                                word_count = len(full_text.split())
                                line_count = len(full_text.split('\n'))
                                
                                # table_utils 관련 통계
                                import table_utils
                                date_matches = len(table_utils.DATE_RE.findall(full_text))
                                bullet_count = sum(full_text.count(bullet) for bullet in table_utils.ALL_BULLETS)
                                
                                st.markdown(f"""
                                **📊 텍스트 통계**
                                - 총 문자 수: {char_count:,}자
                                - 총 단어 수: {word_count:,}개
                                - 총 줄 수: {line_count:,}줄
                                - 날짜 패턴: {date_matches}개
                                - 불릿 포인트: {bullet_count}개
                                """)
                            else:
                                st.warning("문서 텍스트를 찾을 수 없습니다.")
                                
                        except Exception as e:
                            st.error(f"통계 분석 실패: {e}")
            else:
                st.info("분석할 PDF 문서가 없습니다. PDF 파일을 업로드해주세요.")
    
    # 데이터베이스 초기화
    st.divider()
    st.subheader("🗑️ 관리 기능")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🗑️ 모든 문서 삭제", type="secondary", use_container_width=True):
            try:
                vector_store.clear_collection()
                rag_chain.clear_cache()
                st.session_state.processed_files.clear()
                st.session_state.processing_errors.clear()
                st.session_state.document_summaries.clear()  # 요약 캐시도 초기화
                st.success("✅ 모든 문서가 삭제되었습니다.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 초기화 실패: {e}")
    
    with col2:
        if st.button("🔄 캐시 초기화", type="secondary", use_container_width=True):
            try:
                rag_chain.clear_cache()
                st.session_state.processed_files.clear()
                st.session_state.processing_errors.clear()
                st.session_state.document_summaries.clear()  # 문서 요약 캐시도 초기화
                st.success("✅ 캐시가 초기화되었습니다.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 캐시 초기화 실패: {e}")

# 디버그 텍스트 표시 영역 (메인 화면)
if st.session_state.debug_text_display:
    st.markdown("---")
    
    # 헤더와 닫기 버튼
    col1, col2 = st.columns([6, 1])
    with col1:
        st.markdown(f"### {st.session_state.debug_text_title}")
    with col2:
        if st.button("❌ 닫기", key="close_debug_text"):
            st.session_state.debug_text_display = None
            st.session_state.debug_text_type = None
            st.session_state.debug_text_title = None
            st.rerun()
    
    # 텍스트 타입에 따른 스타일링
    if st.session_state.debug_text_type == "raw":
        bg_color = "#f8f9fa"
        border_color = "#dee2e6"
    elif st.session_state.debug_text_type == "structured":
        bg_color = "#f0f8ff"
        border_color = "#007bff"
    else:
        bg_color = "#f8f9fa"
        border_color = "#dee2e6"
    
    # 넓은 텍스트 박스로 표시
    st.markdown(
        f"""
        <div style="background: {bg_color}; padding: 1.5rem; border-radius: 12px; 
                   font-family: 'Courier New', monospace; font-size: 0.9rem; 
                   max-height: 600px; overflow-y: auto; line-height: 1.6; 
                   white-space: pre-wrap; word-wrap: break-word; 
                   border: 2px solid {border_color}; margin: 1rem 0;
                   box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);">
        {st.session_state.debug_text_display}
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.markdown("---")

# 메인 채팅 인터페이스
st.header("💬 RAG 채팅")

# 선택된 문서 요약 표시 (채팅 상단)
if st.session_state.show_document_preview and st.session_state.selected_document:
    doc_name = st.session_state.selected_document
    
# 헤더 부분 간소화
    
    col1, col2 = st.columns([6, 1])
    with col1:
        with st.spinner(f"'{doc_name}' 요약 생성 중..."):
            summary = get_document_summary(doc_name)
            
        # 마크다운이 적용되도록 직접 표시
        st.markdown("---")
        st.markdown(f"**📋 {doc_name} 요약**")
        st.markdown(summary)
        st.markdown("---")
    
    with col2:
        # 답변 생성 중에는 닫기 버튼 비활성화
        close_disabled = st.session_state.is_generating_response
        close_help = "답변 생성 중에는 닫을 수 없습니다" if close_disabled else "요약 닫기"
        
        if st.button("❌", help=close_help, key="close_preview", disabled=close_disabled):
            st.session_state.show_document_preview = False
            st.session_state.selected_document = None
            st.rerun()

# 이전 대화 표시
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 사용자 입력
if prompt := st.chat_input("문서에 대해 질문해보세요..."):
    # 사용자 메시지 추가
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # AI 응답 생성
    with st.chat_message("assistant"):
        # 답변 생성 시작을 표시
        st.session_state.is_generating_response = True
        
        with st.spinner("RAG 시스템으로 답변 생성 중..."):
            try:
                start_time = time.time()
                response = rag_chain.query(prompt)
                end_time = time.time()
                
                # 응답 표시
                st.markdown(response)
                
                # 응답 시간 표시
                response_time = end_time - start_time
                st.caption(f"⏱️ 응답 시간: {response_time:.2f}초")
                
                # 세션에 저장
                st.session_state.messages.append({"role": "assistant", "content": response})
                
            except Exception as e:
                error_msg = f"답변 생성 중 오류가 발생했습니다: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
            finally:
                # 답변 생성 완료를 표시
                st.session_state.is_generating_response = False

# 하단 정보
st.markdown("---")
st.markdown(
    """
    <div style="text-align: center; color: #666;">
        <p>🚀 <strong>RAG 시스템</strong> - 하이브리드 검색, 다단계 추론, 답변 검증</p>
        <p>사용 모델: {model} | 한국어 특화 임베딩 | BM25 + 벡터 검색</p>
    </div>
    """.format(model=OLLAMA_MODEL),
    unsafe_allow_html=True
) 