import logging
from typing import Dict, Any, Optional
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)


class ErrorHandler:
    """에러 처리 및 사용자 친화적 메시지 변환"""
    
    def __init__(self):
        self.error_messages = {
            # 네트워크 에러
            "ConnectionError": "인터넷 연결을 확인해 주세요.",
            "TimeoutError": "요청 시간이 초과되었습니다. 다시 시도해 주세요.",
            "HTTPException": "서버와 통신 중 문제가 발생했습니다.",
            
            # 파일 에러
            "FileNotFoundError": "파일을 찾을 수 없습니다.",
            "PermissionError": "파일 접근 권한이 없습니다.",
            "IOError": "파일을 읽을 수 없습니다.",
            
            # 문서 처리 에러
            "PDFProcessingError": "PDF 파일 처리 중 오류가 발생했습니다.",
            "HWPProcessingError": "HWP 파일 처리 중 오류가 발생했습니다.",
            "DocumentParsingError": "문서 분석 중 오류가 발생했습니다.",
            
            # RAG 시스템 에러
            "EmbeddingError": "문서 임베딩 생성 중 오류가 발생했습니다.",
            "RetrievalError": "문서 검색 중 오류가 발생했습니다.",
            "GenerationError": "답변 생성 중 오류가 발생했습니다.",
            "OllamaError": "AI 모델 연결에 실패했습니다.",
            
            # 검증 에러
            "ValidationError": "입력 데이터가 올바르지 않습니다.",
            "NoEvidenceError": "관련 문서를 찾을 수 없습니다.",
            "HallucinationError": "정확한 답변을 생성할 수 없습니다.",
            
            # 시스템 에러
            "MemoryError": "메모리가 부족합니다.",
            "ResourceError": "시스템 리소스가 부족합니다.",
            "DatabaseError": "데이터베이스 오류가 발생했습니다.",
            
            # 세션 에러
            "SessionNotFoundError": "세션을 찾을 수 없습니다.",
            "SessionExpiredError": "세션이 만료되었습니다.",
            "ConcurrentSessionError": "동시에 여러 요청을 처리할 수 없습니다."
        }
        
        self.error_log = []
        self.max_log_size = 1000
    
    def get_user_message(self, error_type: str, default: Optional[str] = None) -> str:
        """에러 타입에 따른 사용자 친화적 메시지 반환"""
        message = self.error_messages.get(error_type)
        if not message:
            message = default or "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."
        return message
    
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """에러 처리 및 로깅"""
        error_id = datetime.now().isoformat()
        error_type = type(error).__name__
        error_message = str(error)
        stack_trace = traceback.format_exc()
        
        # 로깅
        logger.error(f"Error ID: {error_id}")
        logger.error(f"Type: {error_type}")
        logger.error(f"Message: {error_message}")
        logger.error(f"Context: {context}")
        logger.error(f"Stack trace:\n{stack_trace}")
        
        # 에러 기록 저장
        self.log_error({
            "id": error_id,
            "type": error_type,
            "message": error_message,
            "context": context,
            "timestamp": datetime.now().isoformat(),
            "stack_trace": stack_trace
        })
        
        # 사용자 메시지 생성
        user_message = self.get_user_message(error_type)
        
        return {
            "error_id": error_id,
            "user_message": user_message,
            "error_type": error_type,
            "technical_message": error_message,
            "retry_available": self.is_retry_available(error_type),
            "support_action": self.get_support_action(error_type)
        }
    
    def log_error(self, error_data: Dict[str, Any]):
        """에러 로그 저장"""
        self.error_log.append(error_data)
        
        # 로그 크기 제한
        if len(self.error_log) > self.max_log_size:
            self.error_log = self.error_log[-self.max_log_size:]
    
    def is_retry_available(self, error_type: str) -> bool:
        """재시도 가능 여부 판단"""
        retryable_errors = [
            "TimeoutError",
            "ConnectionError",
            "HTTPException",
            "OllamaError",
            "RetrievalError",
            "GenerationError"
        ]
        return error_type in retryable_errors
    
    def get_support_action(self, error_type: str) -> Dict[str, str]:
        """에러에 따른 지원 액션 제공"""
        actions = {
            "ConnectionError": {
                "action": "retry",
                "label": "다시 시도",
                "description": "인터넷 연결 확인 후 다시 시도하세요"
            },
            "FileNotFoundError": {
                "action": "upload",
                "label": "파일 다시 선택",
                "description": "다른 파일을 선택해 주세요"
            },
            "NoEvidenceError": {
                "action": "rephrase",
                "label": "질문 수정",
                "description": "다른 방식으로 질문해 보세요"
            },
            "SessionExpiredError": {
                "action": "new_session",
                "label": "새 대화 시작",
                "description": "새로운 대화를 시작하세요"
            },
            "OllamaError": {
                "action": "check_service",
                "label": "서비스 상태 확인",
                "description": "AI 서비스 상태를 확인 중입니다"
            }
        }
        
        return actions.get(error_type, {
            "action": "contact",
            "label": "문의하기",
            "description": "지속적인 문제 발생 시 관리자에게 문의하세요"
        })
    
    def handle_validation_error(self, field: str, value: Any, requirement: str) -> str:
        """입력 검증 에러 처리"""
        messages = {
            "query": {
                "empty": "메시지를 입력해 주세요.",
                "too_long": "메시지가 너무 깁니다. 짧게 나누어 보내주세요.",
                "invalid_chars": "사용할 수 없는 문자가 포함되어 있습니다."
            },
            "file": {
                "too_large": "파일이 너무 큽니다. 10MB 이하 파일을 선택해 주세요.",
                "invalid_type": "지원하지 않는 파일 형식입니다. PDF 또는 HWP 파일을 선택해 주세요.",
                "corrupt": "파일이 손상되었습니다. 다른 파일을 선택해 주세요."
            },
            "session": {
                "not_found": "세션을 찾을 수 없습니다. 새 대화를 시작해 주세요.",
                "expired": "세션이 만료되었습니다. 다시 로그인해 주세요."
            }
        }
        
        field_messages = messages.get(field, {})
        return field_messages.get(requirement, f"{field} 입력이 올바르지 않습니다.")
    
    def handle_rag_error(self, error: Exception) -> str:
        """RAG 시스템 에러 처리"""
        error_str = str(error).lower()

        # 에러 로깅 추가
        logger.error(f"RAG Error Type: {type(error).__name__}")
        logger.error(f"RAG Error Message: {error_str}")

        if "ollama" in error_str:
            return "AI 모델에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요."
        elif "embedding" in error_str:
            return "문서 처리 중 오류가 발생했습니다. 다시 시도해 주세요."
        elif "retrieval" in error_str or "search" in error_str:
            return "문서 검색 중 오류가 발생했습니다. 다시 시도해 주세요."
        elif "generation" in error_str:
            return "답변 생성 중 오류가 발생했습니다. 다시 시도해 주세요."
        elif "no evidence" in error_str or "no document" in error_str:
            return "업로드된 문서에서 관련 정보를 찾을 수 없습니다."
        elif "hallucination" in error_str:
            return "정확한 답변을 생성할 수 없습니다. 질문을 다시 입력해 주세요."
        else:
            # 기본 메시지 대신 구체적인 에러 정보 포함
            return f"응답 생성 중 오류가 발생했습니다: {error_str[:100]}"
    
    def get_error_stats(self) -> Dict[str, Any]:
        """에러 통계 반환"""
        if not self.error_log:
            return {
                "total_errors": 0,
                "error_types": {},
                "recent_errors": []
            }
        
        error_types = {}
        for error in self.error_log:
            error_type = error.get("type", "Unknown")
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        recent_errors = self.error_log[-10:]  # 최근 10개
        
        return {
            "total_errors": len(self.error_log),
            "error_types": error_types,
            "recent_errors": [
                {
                    "id": e.get("id"),
                    "type": e.get("type"),
                    "timestamp": e.get("timestamp"),
                    "message": e.get("message")[:100]  # 메시지 요약
                }
                for e in recent_errors
            ]
        }
    
    def clear_error_log(self):
        """에러 로그 초기화"""
        self.error_log = []
        logger.info("Error log cleared")