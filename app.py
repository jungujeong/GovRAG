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

from utils import DocumentProcessor, VectorStore, RAGChain
from config import DOCUMENTS_PATH, logger, OLLAMA_MODEL, set_session_context

# 전역 큐 및 결과 저장을 위한 변수들
processing_queue = queue.Queue()  # 처리할 작업 큐
result_queue = queue.Queue()  # 결과를 저장할 큐
processing_lock = Lock()  # 스레드간 동기화를 위한 락
processing_done_flag = Event()  # 처리 완료 신호용 이벤트
processing_done_flag.set()  # 초기 상태는 완료 상태

# 각 사용자 세션에 고유 ID 할당
if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    # IP 주소 또는 기타 사용자 식별 정보가 있다면 사용
    user_ip = os.environ.get('REMOTE_ADDR', None)
    username = os.environ.get('REMOTE_USER', None)
    user_id = username or user_ip or f"user-{st.session_state.session_id[:8]}"
    st.session_state.user_id = user_id
    
    # 세션 컨텍스트에 사용자 정보 설정
    set_session_context(st.session_state.session_id, st.session_state.user_id)
    
    logger.info(f"새 사용자 세션 시작: {st.session_state.user_id}")

# Configure Streamlit
st.set_page_config(
    page_title="HWP 문서 기반 챗봇",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables
if "messages" not in st.session_state:
    st.session_state.messages = []
if "processing_done" not in st.session_state:
    st.session_state.processing_done = True
if "processed_files" not in st.session_state:
    st.session_state.processed_files = set()
if "processing_files" not in st.session_state:
    st.session_state.processing_files = set()
if "processing_errors" not in st.session_state:
    st.session_state.processing_errors = {}
if "files_to_process" not in st.session_state:
    st.session_state.files_to_process = []
if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False
if "check_processing" not in st.session_state:
    st.session_state.check_processing = False
if "last_processing_time" not in st.session_state:
    st.session_state.last_processing_time = time.time()
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = "file_uploader_1"
if "thread_executor" not in st.session_state:
    st.session_state.thread_executor = None

# Initialize components
@st.cache_resource
def initialize_components():
    """서비스에 필요한 컴포넌트 초기화"""
    # 세션 컨텍스트 업데이트
    if 'session_id' in st.session_state and 'user_id' in st.session_state:
        set_session_context(st.session_state.session_id, st.session_state.user_id)
    
    # 컴포넌트 초기화
    document_processor = DocumentProcessor()
    vector_store = VectorStore()
    rag_chain = RAGChain(vector_store=vector_store.vector_db)
    
    return document_processor, vector_store, rag_chain

# 전역 변수로 먼저 선언
global document_processor, vector_store, rag_chain
document_processor, vector_store, rag_chain = initialize_components()

# 벡터 DB 초기화 상태를 추적하기 위한 세션 상태 변수 추가
if "vector_db_cleared" not in st.session_state:
    st.session_state.vector_db_cleared = False

# 벡터 DB가 초기화된 후 컴포넌트 재초기화를 위한 함수
def reinitialize_components():
    # Clear the cache to force component re-initialization
    st.cache_resource.clear()
    # Return new instances
    document_processor = DocumentProcessor()
    vector_store = VectorStore()
    rag_chain = RAGChain(vector_store=vector_store.vector_db)
    return document_processor, vector_store, rag_chain

# CSS for better UI
st.markdown(
    """
    <style>
    .stApp {
        max-width: 1200px;
        margin: 0 auto;
    }
    .chat-message {
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin-bottom: 1rem;
        display: flex;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }
    .chat-message.user {
        background-color: #f0f2f6;
        color: #000000;
    }
    .chat-message.assistant {
        background-color: #e6f3ff;
        color: #000000;
    }
    .chat-message .message {
        flex-grow: 1;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Function to add new document to vector store
def add_document_to_vectorstore(file_path, file_name):
    try:
        # 새로운 process_document 메서드를 사용하여 텍스트 추출 및 요약
        text, summary = document_processor.process_document(file_path)
        
        # 텍스트 추출 실패 시 
        if not text or not isinstance(text, str):
            error_msg = f"문서 '{file_name}'에서 텍스트를 추출할 수 없습니다."
            logger.error(error_msg)
            return False, error_msg
        
        # 메타데이터 설정
        metadata = {
            "source": file_name,
            "summary": summary[:500] if summary else ""  # 요약 메타데이터 추가 (길이 제한)
        }
        
        # 문서 길이와 기본 정보 기록
        logger.info(f"문서 '{file_name}' 추가 시작 (길이: {len(text)} 문자)")
        
        # 여러 번 시도 
        max_retries = 3
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # 벡터 스토어에 추가
                vector_store.add_document(text, metadata)
                logger.info(f"Document {file_name} successfully added to vector store")
                return True, None
            except Exception as e:
                last_error = str(e)
                error_msg = last_error.lower()
                logger.error(f"문서 추가 시도 {attempt+1}/{max_retries} 실패: {e}")
                
                # 오류 유형에 따른 처리
                if "connection" in error_msg or "timeout" in error_msg:
                    # 연결 문제는 잠시 대기 후 재시도
                    time.sleep(1.0)
                elif "duplicate" in error_msg:
                    # 이미 존재하는 문서이면 성공으로 처리
                    logger.warning(f"문서 '{file_name}'이(가) 이미 벡터 저장소에 존재합니다.")
                    return True, None
                else:
                    # 기타 오류는 마지막 시도까지 계속 재시도
                    time.sleep(0.5)
        
        # 모든 시도 실패 후
        error_msg = f"모든 시도 실패: 문서 '{file_name}'을(를) 벡터 저장소에 추가할 수 없습니다. 오류: {last_error}"
        logger.error(error_msg)
        return False, error_msg
    
    except Exception as e:
        error_msg = f"문서 처리 중 오류 발생: {e}"
        logger.error(error_msg)
        return False, error_msg

# 단일 파일 처리 함수 (ThreadPoolExecutor에서 사용)
def process_single_document(file_item, session_id, user_id):
    file_path, file_name = file_item
    
    # 세션 컨텍스트 설정
    set_session_context(session_id, user_id)
    
    try:
        logger.info(f"벡터 DB에 '{file_name}' 처리 시작")
        success, error_msg = add_document_to_vectorstore(file_path, file_name)
        
        # 결과를 직접 반환 (큐를 사용하지 않음)
        logger.info(f"{'Successfully processed' if success else 'Failed to process'} document: {file_name}")
        
        # 처리 결과를 반환
        return {
            "file_name": file_name,
            "success": success,
            "error": error_msg,
            "timestamp": time.time()
        }
    
    except Exception as e:
        error_msg = f"파일 '{file_name}' 처리 중 오류: {e}"
        logger.error(error_msg)
        
        # 오류 정보를 반환
        return {
            "file_name": file_name,
            "success": False,
            "error": error_msg,
            "timestamp": time.time()
        }

# 개선된 문서 처리 스레드 함수
def process_documents_thread(session_id, user_id):
    """
    문서 처리를 위한 백그라운드 스레드 함수
    
    Args:
        session_id (str): 세션 ID
        user_id (str): 사용자 ID
    """
    global processing_done_flag
    
    files_list = list(processing_queue.queue)
    
    logger.info(f"문서 처리 스레드 시작: {len(files_list)}개 파일")
    
    # 세션 컨텍스트 설정
    set_session_context(session_id, user_id)
    
    # 처리 중 상태로 설정
    processing_done_flag.clear()
    
    try:
        # ThreadPoolExecutor로 병렬 처리 (max_workers는 파일 수와 CPU 코어 수에 따라 조정)
        with ThreadPoolExecutor(max_workers=min(os.cpu_count() or 2, 4)) as executor:
            # 모든 파일에 대해 작업 제출
            futures = {executor.submit(process_single_document, item, session_id, user_id): item for item in files_list}
            
            # 처리 결과 수집
            for future in futures:
                try:
                    # 결과를 받아서 결과 큐에 추가
                    result = future.result()
                    if result:
                        result_queue.put(result)
                except Exception as e:
                    # 처리 중 발생한 예외 로깅
                    file_path, file_name = futures[future]
                    logger.error(f"파일 '{file_name}' 처리 중 예외 발생: {e}")
                    
                    # 오류 정보도 큐에 추가
                    result_queue.put({
                        "file_name": file_name,
                        "success": False,
                        "error": str(e),
                        "timestamp": time.time()
                    })
        
        # 모든 처리 완료 로그
        logger.info("모든 문서 처리 작업 완료")
    
    except Exception as e:
        logger.error(f"문서 처리 스레드에서 예외 발생: {e}")
    
    finally:
        # 큐 비우기
        while not processing_queue.empty():
            try:
                processing_queue.get(block=False)
                processing_queue.task_done()
            except queue.Empty:
                break
        
        # 처리 완료 표시
        processing_done_flag.set()
        
        # 완료 신호 큐에 추가
        result_queue.put({
            "status": "complete",
            "timestamp": time.time()
        })
        
        logger.info("문서 처리 스레드 종료")

# 처리 결과 확인 함수
def check_processing_results():
    """
    결과 큐에서 처리 결과를 확인하고 상태를 업데이트하는 함수
    """
    update_needed = False
    processed_count = 0
    error_count = 0
    
    # 결과 큐에서 데이터 처리
    while not result_queue.empty():
        try:
            result = result_queue.get(block=False)
            
            # 완료 신호인 경우 처리
            if "status" in result and result["status"] == "complete":
                logger.info("처리 완료 신호 수신")
                # 처리 상태 완료로 변경
                st.session_state.processing_done = True
                st.session_state.processing_complete = True
                st.session_state.check_processing = False
                st.session_state.last_processing_time = result.get("timestamp", time.time())
                return True, "complete"
            
            # 파일 처리 결과인 경우
            file_name = result.get("file_name")
            success = result.get("success", False)
            error = result.get("error")
            timestamp = result.get("timestamp", time.time())
            
            # 마지막 처리 시간 갱신
            st.session_state.last_processing_time = timestamp
            
            # 파일 상태 업데이트
            if file_name and file_name in st.session_state.processing_files:
                st.session_state.processing_files.remove(file_name)
                
                if success:
                    st.session_state.processed_files.add(file_name)
                    processed_count += 1
                    logger.info(f"파일 '{file_name}' 처리 결과 업데이트: 성공")
                else:
                    st.session_state.processing_errors[file_name] = error or "알 수 없는 오류"
                    error_count += 1
                    logger.warning(f"파일 '{file_name}' 처리 결과 업데이트: 실패 ({error})")
            
            update_needed = True
            
        except queue.Empty:
            # 큐가 비어있으면 종료
            break
    
    return update_needed, processed_count

# Start the sidebar
st.sidebar.title("📚 문서 관리")

# 처리 중이라면 상태 확인 모드 활성화
if not st.session_state.processing_done and not st.session_state.check_processing:
    st.session_state.check_processing = True
    st.rerun()

# File upload section
uploaded_files = st.sidebar.file_uploader(
    "HWP/PDF 문서 업로드 (최대 100개)",
    type=["hwp", "pdf"],
    accept_multiple_files=True,
    key=st.session_state.uploader_key
)

if uploaded_files:
    with st.sidebar.expander("업로드할 문서", expanded=True):
        total_files = len(uploaded_files)
        
        # 업로드된 파일 목록 표시
        st.write(f"업로드할 문서 {total_files}개:")
        for file in uploaded_files:
            # 처리 상태에 따라 파일 상태 표시
            if file.name in st.session_state.processed_files:
                st.write(f"- ✅ {file.name} (처리 완료)")
            elif file.name in st.session_state.processing_files:
                st.write(f"- ⏳ {file.name} (처리 중)")
            elif file.name in st.session_state.processing_errors:
                st.write(f"- ❌ {file.name} (오류: {st.session_state.processing_errors[file.name]})")
            else:
                st.write(f"- 📄 {file.name}")
        
        # Process files
        if st.button(f"{total_files}개 문서 처리하기", key="process_files"):
            if st.session_state.processing_done:
                # 처리 전 벡터 DB 상태 확인
                try:
                    # 벡터 DB가 응답하는지 테스트
                    vector_store.similarity_search("test", k=1)
                    logger.info("벡터 DB 상태 확인 완료 - 정상")
                except Exception as e:
                    logger.error(f"벡터 DB 상태 확인 실패: {e}")
                    st.error("벡터 DB 상태가 정상이 아닙니다. 페이지를 새로고침하거나 벡터 DB 초기화 후 다시 시도해주세요.")
                    time.sleep(2)
                    st.rerun()
                
                # 처리 상태 초기화
                st.session_state.processing_done = False
                st.session_state.processing_complete = False
                st.session_state.check_processing = True
                
                # 처리 목록 초기화
                st.session_state.processing_files = set()
                st.session_state.processed_files = set()
                st.session_state.processing_errors = {}
                st.session_state.last_processing_time = time.time()
                
                # 이전 결과 큐 비우기
                while not result_queue.empty():
                    try:
                        result_queue.get(block=False)
                    except:
                        pass
                
                # 파일 목록 저장
                files_to_process = [file.name for file in uploaded_files]
                st.session_state.files_to_process = files_to_process
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # 기존 스레드 처리 중지 (있는 경우)
                if not processing_done_flag.is_set():
                    processing_done_flag.set()
                
                successful_uploads = 0
                for i, file in enumerate(uploaded_files):
                    status_text.text(f"처리 중: {file.name} ({i+1}/{total_files})")
                    
                    # 처리 중인 파일 목록에 추가
                    st.session_state.processing_files.add(file.name)
                    
                    try:
                        # 파일 저장 (임시 디렉토리에)
                        os.makedirs(document_processor.documents_path, exist_ok=True)
                        file_path = os.path.join(document_processor.documents_path, file.name)
                        
                        # 파일 저장
                        with open(file_path, 'wb') as f:
                            f.write(file.getbuffer())
                        
                        # 파일 유효성 검사
                        is_valid, message = document_processor.validate_file(file_path)
                        if is_valid:
                            # 유효한 파일은 처리 큐에 추가
                            processing_queue.put((file_path, file.name))
                            successful_uploads += 1
                        else:
                            st.sidebar.error(f"문서 유효성 검사 실패: {file.name} - {message}")
                            # 처리 오류 기록
                            st.session_state.processing_errors[file.name] = message
                            # 실패한 파일은 처리 중 목록에서 제거
                            st.session_state.processing_files.remove(file.name)
                            # 저장된 파일 삭제
                            try:
                                os.remove(file_path)
                            except:
                                pass
                    except Exception as e:
                        error_msg = str(e)
                        st.sidebar.error(f"문서 저장 실패: {file.name} - {error_msg}")
                        # 처리 오류 기록
                        st.session_state.processing_errors[file.name] = error_msg
                        # 실패한 파일은 처리 중 목록에서 제거
                        st.session_state.processing_files.remove(file.name)
                    
                    # Update progress
                    progress_bar.progress((i + 1) / total_files)
                
                # 큐가 비어있는지 확인
                if processing_queue.empty():
                    st.error("업로드할 문서가 없거나 모든 문서 저장에 실패했습니다.")
                    st.session_state.processing_done = True
                    st.session_state.processing_complete = False
                    st.session_state.check_processing = False
                    time.sleep(2)
                    st.rerun()
                
                # 처리 시작 상태로 설정
                processing_done_flag.clear()
                
                # 실제 세션 ID와 사용자 ID 가져오기
                session_id = st.session_state.session_id
                user_id = st.session_state.user_id
                
                # 새 스레드 시작 (세션 ID와 사용자 ID 직접 전달)
                processing_thread = Thread(target=process_documents_thread, args=(session_id, user_id))
                processing_thread.daemon = True
                processing_thread.start()
                
                # 스레드 추적을 위해 저장
                st.session_state.thread_executor = processing_thread
                
                # 처리 상태 업데이트
                st.session_state.check_processing = True
                st.session_state.last_processing_time = time.time()
                
                status_text.text(f"{successful_uploads}/{total_files} 문서 저장 완료. 벡터 DB 처리 중...")
                
                # 상태 메시지 업데이트 및 UI 재로드
                if successful_uploads > 0:
                    st.sidebar.info("📋 문서가 저장되었습니다. 벡터 DB에 처리 중입니다...")
                    st.sidebar.warning("⚠️ 처리가 완료될 때까지 이 페이지를 닫지 마세요.")
                    
                    # 처리 상태 확인 활성화
                    st.session_state.check_processing = True
                    
                    # 새로고침으로 처리 상태 표시 초기화
                    time.sleep(1.0)
                    st.rerun()
                else:
                    st.sidebar.error("❌ 문서 저장에 실패했습니다. 다시 시도해주세요.")
            else:
                st.warning("이미 문서 처리가 진행 중입니다. 완료될 때까지 기다려주세요.")

# 처리 완료 확인 및 UI 업데이트
if st.session_state.check_processing:
    # 현재 시간 기록하여 타임아웃 계산에 사용
    current_time = time.time()
    
    # 결과 큐에서 처리 결과 확인
    update_needed, result_status = check_processing_results()
    
    # 완료 신호를 받은 경우
    if result_status == "complete":
        st.rerun()
    
    # 처리 타임아웃 확인 (더 긴 시간으로 조정 - 60초)
    timeout_seconds = 60
    if (current_time - st.session_state.last_processing_time > timeout_seconds) and st.session_state.processing_files:
        logger.warning(f"{timeout_seconds}초 동안 처리 결과가 없어 타임아웃 발생. 남은 파일: {st.session_state.processing_files}")
        
        # 남은 처리 중 파일을 오류로 표시
        for file_name in list(st.session_state.processing_files):
            st.session_state.processing_files.remove(file_name)
            st.session_state.processing_errors[file_name] = "처리 시간 초과"
            logger.warning(f"타임아웃으로 인해 파일 '{file_name}'의 처리를 실패로 표시")
        
        # 타임아웃으로 모든 처리 완료로 표시
        st.session_state.processing_done = True
        st.session_state.processing_complete = True
        st.session_state.check_processing = False
        st.rerun()
    
    # 스레드 종료 감지
    if processing_done_flag.is_set() and st.session_state.processing_files:
        logger.info("처리 스레드 종료 감지, 남은 파일 상태 업데이트 중")
        
        # 결과 큐에서 모든 결과를 처리한 후 남은 파일 처리
        # 추가 시간을 주어 큐의 모든 결과가 처리되도록 함
        time.sleep(1.0)
        update_needed, _ = check_processing_results()
        
        # 추가 처리 후에도 남은 파일이 있다면 오류로 처리
        remaining_files = list(st.session_state.processing_files)
        if remaining_files:
            for file_name in remaining_files:
                # 파일이 실제로 성공적으로 처리되었는지 확인
                if document_processor.file_exists(file_name):
                    # 파일이 존재하면 이미 처리된 것으로 간주
                    st.session_state.processing_files.remove(file_name)
                    st.session_state.processed_files.add(file_name)
                    logger.info(f"파일 '{file_name}'은(는) 성공적으로 처리되었으나 상태 업데이트가 지연되었습니다.")
                else:
                    # 파일이 존재하지 않으면 실패로 간주
                    st.session_state.processing_files.remove(file_name)
                    st.session_state.processing_errors[file_name] = "처리가 완료되지 않음"
                    logger.warning(f"파일 '{file_name}'의 처리 상태를 실패로 업데이트")
        
        # 처리 완료 상태로 설정
        st.session_state.processing_done = True
        st.session_state.processing_complete = True
        st.session_state.check_processing = False
        st.rerun()
    
    # 모든 파일 처리 완료 확인
    if not st.session_state.processing_files and processing_done_flag.is_set():
        logger.info(f"모든 문서 처리 완료: {len(st.session_state.processed_files)}개 성공, {len(st.session_state.processing_errors)}개 실패")
        st.session_state.processing_done = True
        st.session_state.processing_complete = True
        st.session_state.check_processing = False
        st.rerun()
    
    # 업데이트가 필요한 경우 또는 주기적으로 화면 갱신
    if update_needed or int(time.time()) % 2 == 0:  # 2초마다 한 번씩 강제 갱신
        # 처리 중인 경우 상태 표시 업데이트
        total_to_process = len(st.session_state.files_to_process)
        completed = len(st.session_state.processed_files) + len(st.session_state.processing_errors)
        
        # 처리 중 상태 표시
        with st.sidebar:
            st.write("📊 **문서 처리 현황**")
            progress_bar = st.progress(completed / total_to_process if total_to_process > 0 else 0)
            st.write(f"**{completed}/{total_to_process}** 문서 처리됨 ({int(completed/total_to_process*100 if total_to_process > 0 else 0)}%)")
            
            # 진행 중인 문서 이름 표시 
            if st.session_state.processing_files:
                st.write("**처리 중인 문서:**")
                for file_name in st.session_state.processing_files:
                    st.write(f"- ⏳ {file_name}")
                    
            # 이미 처리된 문서 표시
            if st.session_state.processed_files:
                st.write("**처리 완료된 문서:**")
                for file_name in st.session_state.processed_files:
                    st.write(f"- ✅ {file_name}")
            
            # 오류 발생 문서 표시
            if st.session_state.processing_errors:
                st.write("**오류 발생 문서:**")
                for file_name, error in st.session_state.processing_errors.items():
                    st.write(f"- ❌ {file_name}: {error[:50]}{'...' if len(error) > 50 else ''}")
            
            # 수동 새로고침 버튼
            col1, col2 = st.columns([3, 1])
            with col2:
                if st.button("🔄 새로고침", key="refresh_status"):
                    st.session_state.check_processing = True
                    st.rerun()
        
        # 주기적 자동 새로고침 (더 짧은 간격)
        time.sleep(0.5)
        st.rerun()

# Document management section
with st.sidebar.expander("문서 관리", expanded=True):
    doc_list = document_processor.list_documents()
    
    if doc_list:
        st.write(f"총 {len(doc_list)}개 문서")
        
        # List documents with delete buttons
        for doc in doc_list:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.write(doc)
            with col2:
                if st.button("삭제", key=f"delete_{doc}"):
                    if document_processor.delete_document(doc, vector_store=vector_store):
                        st.success(f"{doc} 삭제 완료")
                        st.rerun()
                    else:
                        st.error(f"{doc} 삭제 실패")
    else:
        st.write("문서가 없습니다.")

# Document summarization
with st.sidebar.expander("문서 요약", expanded=True):
    # 사용 가능한 문서 목록 갱신 (최신 상태 유지)
    available_docs = document_processor.list_documents()
    
    # 세션 상태에 요약 작업 진행중 상태 저장
    if "summarizing" not in st.session_state:
        st.session_state.summarizing = False
    if "cancel_summary" not in st.session_state:
        st.session_state.cancel_summary = False
    
    docs_to_summarize = st.selectbox(
        "요약할 문서 선택",
        options=available_docs,
        key="summary_doc_select"
    )
    
    # 요약 전 문서 정보 미리보기
    if docs_to_summarize:
        try:
            doc_path = document_processor.get_document_path(docs_to_summarize)
            file_size = Path(doc_path).stat().st_size / (1024 * 1024)  # MB 단위
            
            st.write(f"**선택된 파일 정보:**")
            st.write(f"- 파일명: {docs_to_summarize}")
            st.write(f"- 크기: {file_size:.2f} MB")
            
            # 예상 요약 시간 계산
            est_summary_time = max(5, min(120, file_size * 3))  # 파일 크기에 비례한 예상 시간
            if file_size > 5:  # 5MB보다 큰 파일
                st.warning(f"⚠️ 큰 파일입니다. 요약에 {est_summary_time:.0f}초 정도 소요될 수 있습니다.")
            
            # 파일 형식에 따른 추가 정보
            if docs_to_summarize.lower().endswith('.hwp'):
                st.write(f"- 형식: 한글 문서 (HWP)")
            elif docs_to_summarize.lower().endswith('.pdf'):
                st.write(f"- 형식: PDF 문서")
        except Exception as e:
            logger.error(f"Error getting document info: {e}")
            st.warning("문서 정보를 불러올 수 없습니다.")
    
    # 취소 버튼과 요약 버튼
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if docs_to_summarize and not st.session_state.summarizing:
            if st.button("요약하기", key="summarize_btn"):
                st.session_state.summarizing = True
                st.session_state.cancel_summary = False
                st.rerun()
        
    with col2:
        if st.session_state.summarizing:
            if st.button("취소", key="cancel_btn"):
                st.session_state.cancel_summary = True
                st.rerun()
    
    # 요약 프로세스
    if st.session_state.summarizing:
        # 상태 컨테이너
        status_container = st.empty()
        progress_bar = st.empty()
        result_container = st.empty()
        
        try:
            # 1단계: 문서 로딩
            status_container.info("📄 **1/3 단계: 문서 로딩 중...**")
            progress_bar.progress(10)
            
            # 취소 확인
            if st.session_state.cancel_summary:
                status_container.warning("❌ 요약이 취소되었습니다.")
                st.session_state.summarizing = False
                st.session_state.cancel_summary = False
                time.sleep(1)
                st.rerun()
            
            doc_path = document_processor.get_document_path(docs_to_summarize)
            start_time = time.time()
            
            # 2단계: 텍스트 추출
            status_container.info("📝 **2/3 단계: 텍스트 추출 중...**")
            progress_bar.progress(30)
            
            # 취소 확인
            if st.session_state.cancel_summary:
                status_container.warning("❌ 요약이 취소되었습니다.")
                st.session_state.summarizing = False
                st.session_state.cancel_summary = False
                time.sleep(1)
                st.rerun()
                
            document_text, metadata = document_processor.extract_text(doc_path)
            
            if not document_text or not isinstance(document_text, str):
                result_container.error("⚠️ 문서에서 텍스트를 추출할 수 없습니다.")
                st.session_state.summarizing = False
            else:
                # 텍스트 길이 계산 및 예상 시간 추정
                word_count = len(document_text.split())
                char_count = len(document_text)
                
                # 대략적인 예상 시간 (단어 수에 비례)
                est_time_seconds = max(5, min(120, word_count / 500))
                
                # 문서 정보 표시
                info_text = f"""
                **문서 정보:**
                - 단어 수: {word_count:,}개
                - 문자 수: {char_count:,}자
                - 추출 시간: {time.time() - start_time:.2f}초
                """
                result_container.info(info_text)
                
                # 3단계: 요약 생성
                status_container.info(f"🤖 **3/3 단계: 요약 생성 중... (예상 시간: {est_time_seconds:.1f}초)**")
                
                # 취소 확인
                if st.session_state.cancel_summary:
                    status_container.warning("❌ 요약이 취소되었습니다.")
                    st.session_state.summarizing = False
                    st.session_state.cancel_summary = False
                    time.sleep(1)
                    st.rerun()
                
                # 진행 상태 업데이트
                # 이전의 변수 i와 step_count가 정의되지 않은 상태로 사용되어 오류 발생
                step_count = min(20, int(est_time_seconds / 1.5))
                for i in range(30, 95, int(65/step_count) if step_count > 0 else 65):
                    if st.session_state.cancel_summary:
                        status_container.warning("❌ 요약이 취소되었습니다.")
                        st.session_state.summarizing = False
                        st.session_state.cancel_summary = False
                        time.sleep(1)
                        st.rerun()
                    
                    progress_bar.progress(i)
                    time.sleep(est_time_seconds / step_count if step_count > 0 else 0.1)
                
                # 요약 생성
                if not st.session_state.cancel_summary:
                    # 세션 컨텍스트 업데이트
                    set_session_context(st.session_state.session_id, st.session_state.user_id)
                    
                    # 요약 실행 (타임아웃 설정)
                    try:
                        logger.info(f"문서 요약 시작: {docs_to_summarize}")
                        summary = rag_chain.summarize(document_text)
                        logger.info(f"문서 요약 완료: {docs_to_summarize}")
                    except Exception as e:
                        logger.error(f"Summarization error: {e}")
                        status_container.error("⏱️ 요약 생성 중 오류가 발생했습니다.")
                        st.session_state.summarizing = False
                        time.sleep(1)
                        st.rerun()
                
                    # 완료
                    progress_bar.progress(100)
                    status_container.success(f"✅ **요약 완료! (소요 시간: {time.time() - start_time:.2f}초)**")
                    
                    # 주요 키워드 추출 (간단한 빈도 기반)
                    import re
                    from collections import Counter
                    
                    # 한글/영어 혼합 텍스트 처리
                    # 한글 단어 및 영어 단어 추출 (2글자 이상)
                    words = re.findall(r'[가-힣]{2,}|[a-zA-Z]{2,}', document_text.lower())
                    
                    # 한국어 불용어 리스트 (필요에 따라 확장)
                    stopwords = {'그', '이', '저', '것', '수', '등', '들', '및', '에서', '또는', '그리고', '그러나', '이런', '저런',
                                '하다', '있다', '되다', '통해', '위해', '이나', '하여', '하지', '하게', '하면', '해서', '이러한',
                                '그러한', '때문', '그것', '이것', '저것', '우리', '당신', '자신', '스스로', '하기', '한다', '할', '입니다'}
                    
                    filtered_words = [w for w in words if w not in stopwords]
                    keywords = Counter(filtered_words).most_common(10)
                    
                    # 문서 유형에 따른 추가 정보
                    doc_type_info = ""
                    if docs_to_summarize.lower().endswith('.hwp'):
                        doc_type_info = "한글 문서(HWP)는 국내에서 널리 사용되는 문서 형식입니다."
                    elif docs_to_summarize.lower().endswith('.pdf'):
                        doc_type_info = "PDF는 플랫폼 독립적인, 이식성 있는 문서 형식입니다."
                    
                    # 키워드가 없는 경우 처리
                    keyword_text = "추출된 키워드가 없습니다." if not keywords else f"주요 키워드: {', '.join([f'{k}({v}회)' for k, v in keywords])}"
                    
                    # 결과 표시 (개선된 형식)
                    result_html = f"""
                    <div style="border-left: 3px solid #4CAF50; padding-left: 15px; margin: 10px 0;">
                    <h4>📑 {docs_to_summarize} 요약</h4>
                    <p>{summary}</p>
                    <hr style="border-top: 1px solid #eee;">
                    <p><b>📊 문서 분석:</b></p>
                    <ul>
                    <li><b>유형:</b> {docs_to_summarize.split('.')[-1].upper()} 문서</li>
                    <li><b>단어 수:</b> {word_count:,}개</li>
                    <li><b>문자 수:</b> {char_count:,}자</li>
                    <li><b>처리 시간:</b> {time.time() - start_time:.2f}초</li>
                    <li><b>{keyword_text}</b></li>
                    </ul>
                    <p><small>{doc_type_info}</small></p>
                    </div>
                    """
                    result_container.markdown(result_html, unsafe_allow_html=True)
                    
                    # 요약 완료 후 상태 초기화
                    st.session_state.summarizing = False
                    
        except Exception as e:
            logger.error(f"Error summarizing document: {e}")
            progress_bar.empty()
            
            # 오류 유형별 메시지
            error_message = str(e).lower()
            if "timeout" in error_message:
                status_container.error("⏱️ 요약 시간이 초과되었습니다. 문서가 너무 큽니다.")
            elif "permission" in error_message:
                status_container.error("🔒 파일 접근 권한이 없습니다.")
            elif "not found" in error_message or "file" in error_message:
                status_container.error("🔍 파일을 찾을 수 없습니다. 파일이 삭제되었을 수 있습니다.")
            elif "format" in error_message:
                status_container.error("📋 파일 형식이 지원되지 않거나 손상되었습니다.")
            else:
                status_container.error(f"❌ 요약 중 오류 발생: {str(e)}")
                
            # 오류 해결 제안
            suggestions = """
            **시도해 볼 수 있는 방법:**
            1. 다른 문서를 선택해보세요.
            2. 문서 크기가 작은 파일을 시도해보세요.
            3. 파일이 손상되었다면 다시 업로드해보세요.
            """
            result_container.warning(suggestions)
            
            # 오류 발생 시 상태 초기화
            st.session_state.summarizing = False

# 디버깅 도구를 맨 아래로 이동 (접었다 펼칠 수 있게)
with st.sidebar.expander("🛠️ 디버깅 도구", expanded=False):
    # hwplib 초기화 상태 확인 버튼
    if st.button("HWP 처리 모듈 상태 확인", key="check_hwplib"):
        with st.spinner("hwplib 상태 확인 중..."):
            try:
                if document_processor.hwp_extractor:
                    st.success("hwplib가 정상적으로 초기화되었습니다.")
                    st.info("HWP 파일 처리가 가능합니다.")
                else:
                    st.error("hwplib가 초기화되지 않았습니다.")
                    st.warning("HWP 파일 처리가 불가능합니다. Java 설치 및 hwplib JAR 파일 설정을 확인하세요.")
            except Exception as e:
                st.error(f"초기화 상태 확인 중 오류 발생: {str(e)}")
    
    st.markdown("---")
    st.write("⚠️ **주의**: 아래 기능은 모든 데이터를 삭제합니다")
    
    if st.button("벡터 DB 초기화", key="clear_vector_db"):
        with st.spinner("벡터 DB 초기화 중..."):
            try:
                # 파일 목록 조회 (기존 document_processor.list_documents 메서드 대신 직접 구현)
                doc_files = [f for f in os.listdir(document_processor.documents_path) 
                             if f.lower().endswith(('.hwp', '.pdf'))]
                deleted_count = 0
                
                if doc_files:
                    for doc_file in doc_files:
                        # 파일 삭제 시도
                        try:
                            file_path = os.path.join(document_processor.documents_path, doc_file)
                            os.remove(file_path)
                            deleted_count += 1
                        except Exception as e:
                            logger.error(f"파일 삭제 실패: {doc_file} - {e}")
                
                # 벡터 DB 초기화 시도
                success = vector_store.clear()
                
                if success:
                    if deleted_count > 0:
                        st.success(f"벡터 DB가 초기화되고, {deleted_count}개 문서 파일이 삭제되었습니다.")
                    else:
                        st.success("벡터 DB가 초기화되었습니다. 삭제할 문서 파일이 없습니다.")
                    
                    logger.info(f"Vector DB cleared and {deleted_count} document files deleted by user")
                    
                    # 세션 상태 초기화 - 필요한 경우 추가
                    if "processed_files" in st.session_state:
                        st.session_state.processed_files = set()
                    
                    # 컴포넌트 재초기화를 위해 세션 상태 변수 설정
                    st.session_state.vector_db_cleared = True
                    
                    # 세션 상태 초기화
                    st.session_state.uploader_key = f"file_uploader_{int(time.time())}"
                    
                    # 업로더 관련 상태 초기화
                    for key in list(st.session_state.keys()):
                        if key.startswith("file_uploader") and key != st.session_state.uploader_key:
                            del st.session_state[key]
                    
                    # 2초 후 페이지 새로고침
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error("벡터 DB 초기화 중 오류가 발생했습니다.")
                    logger.error("Failed to clear Vector DB")
            except Exception as e:
                st.error(f"벡터 DB 초기화 중 예외 발생: {str(e)}")
                logger.error(f"Exception during Vector DB clearing: {e}")

# Main chat interface
st.title("📚 HWP 문서 기반 챗봇")
st.write("문서 기반 질의응답 시스템에 질문을 입력하세요.")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Chat input
if prompt := st.chat_input("질문을 입력하세요..."):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message in chat
    with st.chat_message("user"):
        st.write(prompt)
    
    # Display assistant response in chat
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        # Generate assistant response
        try:
            with st.spinner("답변 생성 중..."):
                # 세션 컨텍스트 업데이트
                set_session_context(st.session_state.session_id, st.session_state.user_id)
                
                logger.info(f"질문 입력: '{prompt}'")
                response = rag_chain.query(prompt)
                logger.info(f"응답 생성 완료: {len(response)} 자")
                
                # Simulate streaming effect
                for chunk in response.split():
                    full_response += chunk + " "
                    message_placeholder.write(full_response + "▌")
                    time.sleep(0.01)
                
                message_placeholder.write(response)
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            message_placeholder.write("죄송합니다. 답변 생성 중 오류가 발생했습니다. 다시 시도해주세요.")
            full_response = "죄송합니다. 답변 생성 중 오류가 발생했습니다. 다시 시도해주세요."
    
    # Add assistant response to chat history
    st.session_state.messages.append({"role": "assistant", "content": full_response.strip()})

# Footer
st.markdown("---")
st.caption("HWP 문서 기반 질의응답 시스템 | 모든 문서는 공유되며 벡터 DB에 저장됩니다.")

# 만약 벡터 DB가 초기화되었다면 컴포넌트 재초기화
if st.session_state.vector_db_cleared:
    document_processor, vector_store, rag_chain = reinitialize_components()
    logger.info("벡터 DB 초기화 후 모든 컴포넌트가 재초기화되었습니다.")
    st.session_state.vector_db_cleared = False
    # 벡터 DB 초기화 후 첫 실행 시 상태 메시지 표시
    st.sidebar.success("모든 컴포넌트가 재초기화되었습니다. 새 문서를 업로드해주세요.")
    # 상태 메시지를 위한 시간 지연 없이 즉시 표시

if st.session_state.processing_complete:
    st.sidebar.success("🎉 **모든 문서 처리가 완료되었습니다!**")
    
    # 성공 및 오류 수 표시
    success_count = len(st.session_state.processed_files)
    error_count = len(st.session_state.processing_errors)
    total_count = success_count + error_count
    
    if error_count == 0:
        st.sidebar.info(f"업로드된 모든 문서({success_count}개)가 벡터 DB에 성공적으로 추가되었습니다.")
    else:
        st.sidebar.warning(f"{success_count}/{total_count}개 문서가 추가되었습니다. {error_count}개 문서에 오류가 발생했습니다.")
    
    # 완료 처리
    st.session_state.processing_complete = False
    
    # 업로드된 파일 목록 초기화 (오류 파일은 유지)
    st.session_state.files_to_process = []
    
    # 파일 업로더 상태 초기화 - 키를 변경하여 완전히 새로운 업로더 위젯 생성
    st.session_state.uploader_key = f"file_uploader_{int(time.time())}"
    
    # 세션에서 이전 업로더 키와 관련된 데이터 제거
    for key in list(st.session_state.keys()):
        if key.startswith("file_uploader") and key != st.session_state.uploader_key:
            del st.session_state[key]
    
    # 프론트엔드 갱신 (충분한 시간을 두어 사용자가 메시지를 볼 수 있게 함)
    time.sleep(1.0)
    st.rerun()

if __name__ == "__main__":
    pass 