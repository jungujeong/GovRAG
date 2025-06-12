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
    "enhanced_mode": True
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
        padding: 1rem;
        border-bottom: 1px solid #f1f3f4;
        border-radius: 8px;
        margin-bottom: 0.5rem;
        background: #fafbfc;
        transition: all 0.2s ease;
    }
    
    .file-item:hover {
        background: #f0f2f5;
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
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
    }
    
    .file-name strong {
        color: #495057 !important;
        font-weight: 600 !important;
    }
    
    .file-name small {
        color: #6c757d !important;
        font-size: 0.85rem !important;
    }
    
    .file-actions {
        display: flex;
        gap: 0.5rem;
        align-items: center;
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
        try:
            existing_docs = vector_store.get_document_by_metadata({"source": file_name})
            if existing_docs:
                logger.info(f"기존 문서 발견: {file_name}, 삭제 후 재추가")
                # ChromaDB에서 직접 삭제
                collection = vector_store.vector_store._collection
                delete_results = collection.get(where={"source": file_name})
                if delete_results.get('ids'):
                    collection.delete(ids=delete_results['ids'])
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

# 사이드바 설정
with st.sidebar:
    st.header("📁 문서 업로드")
    
    # 벡터 DB 정보 표시
    try:
        db_info = vector_store.get_collection_info()
        st.markdown(
            f"""
            <div class="stats-container">
                <h4>📊 데이터베이스 상태</h4>
                <p><strong>문서 수:</strong> {db_info.get('document_count', 0)}</p>
                <p><strong>BM25 문서:</strong> {db_info.get('bm25_documents', 0)}</p>
                <p><strong>컬렉션:</strong> {db_info.get('collection_name', 'N/A')}</p>
            </div>
            """,
            unsafe_allow_html=True
        )
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
            
            # 각 문서별로 표시 및 삭제 버튼
            for doc_name, doc_info in documents.items():
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    # 파일 확장자에 따른 아이콘
                    if doc_name.lower().endswith('.pdf'):
                        file_icon = "📄"
                    elif doc_name.lower().endswith('.hwp'):
                        file_icon = "📝"
                    elif doc_name.lower().endswith(('.txt', '.md')):
                        file_icon = "📃"
                    else:
                        file_icon = "📄"
                    
                    st.markdown(
                        f"""
                        <div class="file-item">
                            <div class="file-name">
                                {file_icon} <strong>{doc_name}</strong><br>
                                <small>청크: {doc_info['chunk_count']}개 | 타입: {doc_info['file_type'].upper()}</small>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                
                with col2:
                    if st.button("🗑️", key=f"delete_{doc_name}", help=f"{doc_name} 삭제", use_container_width=True):
                        try:
                            # ChromaDB에서 해당 문서의 모든 청크 삭제
                            delete_results = collection.get(where={"source": doc_name})
                            if delete_results.get('ids'):
                                collection.delete(ids=delete_results['ids'])
                                st.success(f"✅ {doc_name} 삭제 완료")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.warning(f"⚠️ {doc_name}을 찾을 수 없습니다")
                        except Exception as e:
                            st.error(f"❌ 삭제 실패: {e}")
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
                st.success("✅ 캐시가 초기화되었습니다.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ 캐시 초기화 실패: {e}")

# 메인 채팅 인터페이스
st.header("💬 RAG 채팅")

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