import os
from dotenv import load_dotenv, find_dotenv
import uuid
import logging
import time
import threading

# 세션별 사용자 ID를 저장하는 스레드 로컬 저장소
class SessionContext(threading.local):
    def __init__(self):
        super().__init__()
        self.session_id = None
        self.user_id = None

# 세션 컨텍스트 전역 인스턴스
session_context = SessionContext()

# 세션 컨텍스트 설정 함수
def set_session_context(session_id, user_id=None):
    session_context.session_id = session_id
    session_context.user_id = user_id or f"user-{session_id[:8]}"

# Streamlit 세션 정보를 로그에 추가하는 필터
class StreamlitSessionFilter(logging.Filter):
    def filter(self, record):
        # session_id와 user_id 속성이 이미 있는지 확인
        if not hasattr(record, 'session_id'):
            # 세션 정보 추가
            if hasattr(session_context, 'session_id') and session_context.session_id:
                record.session_id = session_context.session_id[:8]  # 앞 8자리만 사용
                record.user_id = session_context.user_id
            else:
                record.session_id = "no-session"
                record.user_id = "system"
        return True

# 명시적으로 .env 파일 경로를 찾고 로드
dotenv_path = find_dotenv(usecwd=True)
if dotenv_path:
    load_dotenv(dotenv_path, override=True)  # override=True로 기존 환경 변수 덮어쓰기
    print(f".env 파일 로드됨: {dotenv_path}")
else:
    print("경고: .env 파일을 찾을 수 없습니다.")

# Ollama configuration
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
# 한국어 성능 개선을 위한 온도 조정 (더 일관된 답변)
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

# Vector store configuration - 한국어 문서 특성에 최적화
VECTOR_DB_PATH = os.getenv("VECTOR_DB_PATH", "./data/vector_db")
# 한국어 문서 특성에 맞게 청크 크기 조정
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "800"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))

# Embedding models configuration
EMBEDDING_MODELS_STR = os.getenv("EMBEDDING_MODELS", "llama2,all-minilm,nomic-embed-text")
EMBEDDING_MODELS = [
    {"model": model, "name": model} for model in EMBEDDING_MODELS_STR.split(",")
]

# Document storage
DOCUMENTS_PATH = "./data/documents"

# Java configuration for hwplib
JAVA_HOME = os.getenv("JAVA_HOME", "")

# Logging configuration
# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 루트 로거 가져오기
root_logger = logging.getLogger()

# 세션 필터 생성
session_filter = StreamlitSessionFilter()

# 로깅 형식 정의 - 세션 정보 포함
formatter = logging.Formatter(
    '%(asctime)s - [%(user_id)s][%(session_id)s] - %(name)s - %(levelname)s - %(message)s',
    '%Y-%m-%d %H:%M:%S'
)

# 모든 핸들러에 대해 필터와 포맷터 적용
for handler in root_logger.handlers:
    handler.addFilter(session_filter)
    handler.setFormatter(formatter)

# 로거 가져오기
logger = logging.getLogger(__name__)

# 루트 로거의 필터를 확인하고 없으면 추가
if not any(isinstance(f, StreamlitSessionFilter) for f in root_logger.filters):
    root_logger.addFilter(session_filter) 