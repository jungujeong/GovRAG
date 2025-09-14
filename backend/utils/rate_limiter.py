import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """API 요청 속도 제한"""
    
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, list] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task = None
    
    async def initialize(self):
        """초기화 및 정리 태스크 시작"""
        self._cleanup_task = asyncio.create_task(self._cleanup_old_requests())
    
    async def shutdown(self):
        """종료 처리"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    async def check_limit(self, identifier: str) -> bool:
        """요청 제한 확인"""
        async with self._lock:
            now = datetime.now()
            
            # 식별자별 요청 기록 초기화
            if identifier not in self.requests:
                self.requests[identifier] = []
            
            # 윈도우 시간 이전 요청 제거
            cutoff_time = now - timedelta(seconds=self.window_seconds)
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if req_time > cutoff_time
            ]
            
            # 제한 확인
            if len(self.requests[identifier]) >= self.max_requests:
                logger.warning(f"Rate limit exceeded for {identifier}")
                return False
            
            # 요청 기록
            self.requests[identifier].append(now)
            return True
    
    async def get_remaining_requests(self, identifier: str) -> int:
        """남은 요청 수 확인"""
        async with self._lock:
            if identifier not in self.requests:
                return self.max_requests
            
            now = datetime.now()
            cutoff_time = now - timedelta(seconds=self.window_seconds)
            valid_requests = [
                req_time for req_time in self.requests[identifier]
                if req_time > cutoff_time
            ]
            
            return max(0, self.max_requests - len(valid_requests))
    
    async def get_reset_time(self, identifier: str) -> Optional[datetime]:
        """제한 리셋 시간 확인"""
        async with self._lock:
            if identifier not in self.requests or not self.requests[identifier]:
                return None
            
            # 가장 오래된 요청 시간 + 윈도우 시간
            oldest_request = min(self.requests[identifier])
            return oldest_request + timedelta(seconds=self.window_seconds)
    
    async def _cleanup_old_requests(self):
        """오래된 요청 기록 정리"""
        while True:
            try:
                await asyncio.sleep(60)  # 1분마다 정리
                
                async with self._lock:
                    now = datetime.now()
                    cutoff_time = now - timedelta(seconds=self.window_seconds)
                    
                    # 각 식별자별로 오래된 요청 제거
                    for identifier in list(self.requests.keys()):
                        self.requests[identifier] = [
                            req_time for req_time in self.requests[identifier]
                            if req_time > cutoff_time
                        ]
                        
                        # 빈 리스트 제거
                        if not self.requests[identifier]:
                            del self.requests[identifier]
                    
                    logger.debug(f"Cleaned up rate limiter. Active identifiers: {len(self.requests)}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Rate limiter cleanup error: {e}")
    
    def reset(self, identifier: Optional[str] = None):
        """제한 초기화"""
        if identifier:
            if identifier in self.requests:
                del self.requests[identifier]
        else:
            self.requests.clear()
    
    def get_stats(self) -> Dict:
        """통계 정보 반환"""
        total_requests = sum(len(reqs) for reqs in self.requests.values())
        return {
            "active_identifiers": len(self.requests),
            "total_requests": total_requests,
            "max_requests_per_window": self.max_requests,
            "window_seconds": self.window_seconds
        }


class IPRateLimiter(RateLimiter):
    """IP 기반 요청 속도 제한"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(max_requests, window_seconds)
    
    def get_client_ip(self, request) -> str:
        """클라이언트 IP 추출"""
        # X-Forwarded-For 헤더 확인 (프록시 환경)
        if "X-Forwarded-For" in request.headers:
            return request.headers["X-Forwarded-For"].split(",")[0].strip()
        # X-Real-IP 헤더 확인
        elif "X-Real-IP" in request.headers:
            return request.headers["X-Real-IP"]
        # 직접 연결
        else:
            return request.client.host if request.client else "unknown"


class UserRateLimiter(RateLimiter):
    """사용자별 요청 속도 제한"""
    
    def __init__(self, max_requests: int = 50, window_seconds: int = 60):
        super().__init__(max_requests, window_seconds)
    
    async def check_user_limit(self, user_id: str, action: str) -> bool:
        """사용자 및 액션별 제한 확인"""
        identifier = f"{user_id}:{action}"
        return await self.check_limit(identifier)