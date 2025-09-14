import asyncio
import hashlib
import json
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """캐시 관리 시스템"""
    
    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_counts: Dict[str, int] = {}
        self.lock = asyncio.Lock()
        self._cleanup_task = None
    
    async def initialize(self):
        """초기화 및 정리 태스크 시작"""
        self._cleanup_task = asyncio.create_task(self._cleanup_expired())
        logger.info(f"CacheManager initialized (max_size={self.max_size}, ttl={self.ttl_seconds}s)")
    
    async def shutdown(self):
        """종료 처리"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
    
    def _generate_key(self, *args, **kwargs) -> str:
        """캐시 키 생성"""
        key_data = {
            'args': args,
            'kwargs': kwargs
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 가져오기"""
        async with self.lock:
            if key in self.cache:
                entry = self.cache[key]
                
                # TTL 확인
                if time.time() - entry['timestamp'] > self.ttl_seconds:
                    del self.cache[key]
                    if key in self.access_counts:
                        del self.access_counts[key]
                    return None
                
                # 액세스 카운트 증가
                self.access_counts[key] = self.access_counts.get(key, 0) + 1
                
                # LRU 업데이트
                entry['last_access'] = time.time()
                
                return entry['value']
            
            return None
    
    async def set(self, key: str, value: Any) -> None:
        """캐시에 값 저장"""
        async with self.lock:
            # 캐시 크기 제한 확인
            if len(self.cache) >= self.max_size and key not in self.cache:
                # LRU 제거
                await self._evict_lru()
            
            self.cache[key] = {
                'value': value,
                'timestamp': time.time(),
                'last_access': time.time()
            }
            self.access_counts[key] = 1
    
    async def delete(self, key: str) -> bool:
        """캐시에서 값 삭제"""
        async with self.lock:
            if key in self.cache:
                del self.cache[key]
                if key in self.access_counts:
                    del self.access_counts[key]
                return True
            return False
    
    async def clear(self) -> None:
        """캐시 전체 초기화"""
        async with self.lock:
            self.cache.clear()
            self.access_counts.clear()
    
    async def _evict_lru(self) -> None:
        """LRU 항목 제거"""
        if not self.cache:
            return
        
        # 가장 오래 액세스된 항목 찾기
        lru_key = min(
            self.cache.keys(),
            key=lambda k: self.cache[k]['last_access']
        )
        
        del self.cache[lru_key]
        if lru_key in self.access_counts:
            del self.access_counts[lru_key]
    
    async def _cleanup_expired(self) -> None:
        """만료된 항목 정리"""
        while True:
            try:
                await asyncio.sleep(60)  # 1분마다 정리
                
                async with self.lock:
                    current_time = time.time()
                    expired_keys = [
                        key for key, entry in self.cache.items()
                        if current_time - entry['timestamp'] > self.ttl_seconds
                    ]
                    
                    for key in expired_keys:
                        del self.cache[key]
                        if key in self.access_counts:
                            del self.access_counts[key]
                    
                    if expired_keys:
                        logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total_hits = sum(self.access_counts.values())
        return {
            'size': len(self.cache),
            'max_size': self.max_size,
            'ttl_seconds': self.ttl_seconds,
            'total_hits': total_hits,
            'hit_rate': total_hits / max(len(self.access_counts), 1),
            'top_accessed': sorted(
                self.access_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }


class CachedFunction:
    """함수 결과 캐싱 데코레이터"""
    
    def __init__(self, cache_manager: CacheManager, ttl: Optional[int] = None):
        self.cache_manager = cache_manager
        self.ttl = ttl
    
    def __call__(self, func: Callable):
        async def wrapper(*args, **kwargs):
            # 캐시 키 생성
            cache_key = self.cache_manager._generate_key(
                func.__name__, *args, **kwargs
            )
            
            # 캐시 확인
            cached_value = await self.cache_manager.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_value
            
            # 함수 실행
            result = await func(*args, **kwargs)
            
            # 결과 캐싱
            await self.cache_manager.set(cache_key, result)
            
            return result
        
        return wrapper


# 전역 캐시 인스턴스들
query_cache = CacheManager(max_size=500, ttl_seconds=1800)  # 30분
document_cache = CacheManager(max_size=100, ttl_seconds=3600)  # 1시간
embedding_cache = CacheManager(max_size=1000, ttl_seconds=7200)  # 2시간