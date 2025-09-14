import re
from typing import Any, Dict, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class InputValidator:
    """입력 검증 유틸리티"""
    
    # 파일 크기 제한 (MB)
    MAX_FILE_SIZE_MB = 10
    
    # 지원 파일 형식
    ALLOWED_FILE_TYPES = {'.pdf', '.hwp'}
    
    # 쿼리 제한
    MIN_QUERY_LENGTH = 1
    MAX_QUERY_LENGTH = 2000
    
    # 세션 제한
    MAX_SESSION_TITLE_LENGTH = 100
    MAX_SESSIONS_PER_USER = 100
    MAX_MESSAGES_PER_SESSION = 1000
    
    # 금지 문자 패턴
    FORBIDDEN_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # XSS
        r'javascript:',  # JavaScript injection
        r'on\w+\s*=',  # Event handlers
        r'<iframe',  # Iframe injection
    ]
    
    @classmethod
    def validate_query(cls, query: str) -> tuple[bool, str]:
        """쿼리 검증"""
        # 빈 쿼리 체크
        if not query or not query.strip():
            return False, "메시지를 입력해 주세요."
        
        # 길이 체크
        if len(query) < cls.MIN_QUERY_LENGTH:
            return False, "메시지가 너무 짧습니다."
        
        if len(query) > cls.MAX_QUERY_LENGTH:
            return False, f"메시지가 너무 깁니다. {cls.MAX_QUERY_LENGTH}자 이하로 입력해 주세요."
        
        # 악성 패턴 체크
        for pattern in cls.FORBIDDEN_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return False, "사용할 수 없는 문자가 포함되어 있습니다."
        
        return True, ""
    
    @classmethod
    def validate_file(cls, file_path: Path) -> tuple[bool, str]:
        """파일 검증"""
        # 파일 존재 확인
        if not file_path.exists():
            return False, "파일을 찾을 수 없습니다."
        
        # 파일 크기 확인
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > cls.MAX_FILE_SIZE_MB:
            return False, f"파일이 너무 큽니다. {cls.MAX_FILE_SIZE_MB}MB 이하 파일을 선택해 주세요."
        
        # 파일 형식 확인
        if file_path.suffix.lower() not in cls.ALLOWED_FILE_TYPES:
            return False, f"지원하지 않는 파일 형식입니다. {', '.join(cls.ALLOWED_FILE_TYPES)} 파일을 선택해 주세요."
        
        # 파일 읽기 가능 확인
        try:
            with open(file_path, 'rb') as f:
                f.read(1)
        except Exception:
            return False, "파일을 읽을 수 없습니다. 다른 파일을 선택해 주세요."
        
        return True, ""
    
    @classmethod
    def validate_session_title(cls, title: str) -> tuple[bool, str]:
        """세션 제목 검증"""
        if not title:
            return True, ""  # 빈 제목 허용
        
        if len(title) > cls.MAX_SESSION_TITLE_LENGTH:
            return False, f"제목이 너무 깁니다. {cls.MAX_SESSION_TITLE_LENGTH}자 이하로 입력해 주세요."
        
        # 악성 패턴 체크
        for pattern in cls.FORBIDDEN_PATTERNS:
            if re.search(pattern, title, re.IGNORECASE):
                return False, "사용할 수 없는 문자가 포함되어 있습니다."
        
        return True, ""
    
    @classmethod
    def sanitize_input(cls, text: str) -> str:
        """입력 텍스트 정제"""
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)
        
        # 제어 문자 제거 (탭, 줄바꿈 제외)
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n')
        
        # 연속 공백 정리
        text = re.sub(r'\s+', ' ', text)
        
        # 앞뒤 공백 제거
        text = text.strip()
        
        return text
    
    @classmethod
    def validate_document_ids(cls, doc_ids: List[str]) -> tuple[bool, str]:
        """문서 ID 목록 검증"""
        if not doc_ids:
            return True, ""  # 빈 목록 허용
        
        # ID 형식 검증 (UUID 또는 알파뉴메릭)
        id_pattern = re.compile(r'^[a-zA-Z0-9\-_]+$')
        for doc_id in doc_ids:
            if not id_pattern.match(doc_id):
                return False, f"잘못된 문서 ID 형식입니다: {doc_id}"
        
        return True, ""
    
    @classmethod
    def validate_pagination(cls, page: int, page_size: int) -> tuple[bool, str]:
        """페이지네이션 파라미터 검증"""
        if page < 1:
            return False, "페이지 번호는 1 이상이어야 합니다."
        
        if page_size < 1 or page_size > 100:
            return False, "페이지 크기는 1-100 사이여야 합니다."
        
        return True, ""


class OutputSanitizer:
    """출력 정제 유틸리티"""
    
    @staticmethod
    def sanitize_for_html(text: str) -> str:
        """HTML 출력용 정제"""
        # HTML 특수문자 이스케이프
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#39;')
        
        return text
    
    @staticmethod
    def sanitize_for_json(text: str) -> str:
        """JSON 출력용 정제"""
        # 제어 문자 제거
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\t\n')
        
        # 백슬래시 이스케이프
        text = text.replace('\\', '\\\\')
        
        return text
    
    @staticmethod
    def mask_pii(text: str) -> str:
        """개인정보 마스킹"""
        # 이메일 마스킹
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        text = re.sub(email_pattern, '[이메일]', text)
        
        # 전화번호 마스킹 (한국 형식)
        phone_pattern = r'(\d{2,3})-?(\d{3,4})-?(\d{4})'
        text = re.sub(phone_pattern, '[전화번호]', text)
        
        # 주민등록번호 마스킹
        rrn_pattern = r'\d{6}-?\d{7}'
        text = re.sub(rrn_pattern, '[주민등록번호]', text)
        
        # 신용카드 번호 마스킹
        card_pattern = r'\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}'
        text = re.sub(card_pattern, '[카드번호]', text)
        
        return text


class ConfigValidator:
    """설정 검증 유틸리티"""
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """설정 검증"""
        errors = []
        
        # 필수 설정 확인
        required_fields = [
            'DOC_DIR',
            'WHOOSH_DIR',
            'CHROMA_DIR',
            'OLLAMA_HOST',
            'OLLAMA_MODEL'
        ]
        
        for field in required_fields:
            if field not in config or not config[field]:
                errors.append(f"{field}가 설정되지 않았습니다.")
        
        # 디렉토리 존재 확인
        dir_fields = ['DOC_DIR', 'WHOOSH_DIR', 'CHROMA_DIR']
        for field in dir_fields:
            if field in config:
                path = Path(config[field])
                if not path.exists():
                    try:
                        path.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        errors.append(f"{field} 디렉토리를 생성할 수 없습니다: {e}")
        
        # 숫자 범위 검증
        numeric_validations = {
            'CHUNK_TOKENS': (100, 10000),
            'CHUNK_OVERLAP': (0, 1000),
            'TOPK_BM25': (1, 100),
            'TOPK_VECTOR': (1, 100),
            'TOPK_RERANK': (1, 50),
            'GEN_TEMPERATURE': (0.0, 2.0),
            'GEN_TOP_P': (0.0, 1.0),
            'GEN_MAX_TOKENS': (100, 4096)
        }
        
        for field, (min_val, max_val) in numeric_validations.items():
            if field in config:
                value = config[field]
                if not isinstance(value, (int, float)):
                    errors.append(f"{field}는 숫자여야 합니다.")
                elif value < min_val or value > max_val:
                    errors.append(f"{field}는 {min_val}-{max_val} 범위여야 합니다.")
        
        # 가중치 합 검증
        weights = ['W_BM25', 'W_VECTOR', 'W_RERANK']
        if all(w in config for w in weights):
            total_weight = sum(config[w] for w in weights)
            if abs(total_weight - 1.0) > 0.01:
                errors.append(f"가중치 합이 1.0이 아닙니다: {total_weight}")
        
        return len(errors) == 0, errors