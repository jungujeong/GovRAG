from typing import Any, Optional, Dict
from functools import lru_cache, wraps
import time
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

class TTLCache:
    """Simple TTL cache implementation"""
    
    def __init__(self, ttl_seconds: int = 300):
        self.cache = {}
        self.ttl = ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any):
        """Set value in cache"""
        self.cache[key] = (value, time.time())
    
    def clear(self):
        """Clear all cache entries"""
        self.cache.clear()
    
    def size(self) -> int:
        """Get cache size"""
        return len(self.cache)

# Global caches
query_cache = TTLCache(ttl_seconds=600)  # 10 minutes
embedding_cache = TTLCache(ttl_seconds=3600)  # 1 hour
document_cache = TTLCache(ttl_seconds=1800)  # 30 minutes

def cache_key(*args, **kwargs) -> str:
    """Generate cache key from arguments"""
    key_data = {
        "args": args,
        "kwargs": kwargs
    }
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()

def cached_result(ttl_seconds: int = 300):
    """Decorator for caching function results"""
    def decorator(func):
        cache = TTLCache(ttl_seconds=ttl_seconds)
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            key = cache_key(*args, **kwargs)
            result = cache.get(key)
            
            if result is None:
                result = await func(*args, **kwargs)
                cache.set(key, result)
                logger.debug(f"Cache miss for {func.__name__}")
            else:
                logger.debug(f"Cache hit for {func.__name__}")
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            key = cache_key(*args, **kwargs)
            result = cache.get(key)
            
            if result is None:
                result = func(*args, **kwargs)
                cache.set(key, result)
                logger.debug(f"Cache miss for {func.__name__}")
            else:
                logger.debug(f"Cache hit for {func.__name__}")
            
            return result
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

class QueryResultCache:
    """Specialized cache for query results"""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 600):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl_seconds
        self.access_count = {}
    
    def get(self, query: str) -> Optional[Dict]:
        """Get cached query result"""
        key = self._normalize_query(query)
        
        if key in self.cache:
            result, timestamp = self.cache[key]
            
            if time.time() - timestamp < self.ttl:
                self.access_count[key] = self.access_count.get(key, 0) + 1
                return result
            else:
                del self.cache[key]
                if key in self.access_count:
                    del self.access_count[key]
        
        return None
    
    def set(self, query: str, result: Dict):
        """Cache query result"""
        key = self._normalize_query(query)
        
        # Evict least accessed if at max size
        if len(self.cache) >= self.max_size:
            self._evict_least_accessed()
        
        self.cache[key] = (result, time.time())
        self.access_count[key] = 1
    
    def _normalize_query(self, query: str) -> str:
        """Normalize query for caching"""
        # Remove extra whitespace and lowercase
        normalized = " ".join(query.lower().split())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _evict_least_accessed(self):
        """Evict least accessed entry"""
        if not self.access_count:
            return
        
        least_accessed = min(self.access_count, key=self.access_count.get)
        
        if least_accessed in self.cache:
            del self.cache[least_accessed]
        if least_accessed in self.access_count:
            del self.access_count[least_accessed]
    
    def clear(self):
        """Clear cache"""
        self.cache.clear()
        self.access_count.clear()
    
    def stats(self) -> Dict:
        """Get cache statistics"""
        total_accesses = sum(self.access_count.values())
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "total_accesses": total_accesses,
            "ttl_seconds": self.ttl
        }

# Global query result cache
query_result_cache = QueryResultCache()

def clear_all_caches() -> List[str]:
    """Clear all application caches"""
    cleared = []
    
    # Clear global caches
    query_cache.clear()
    cleared.append("query_cache")
    
    embedding_cache.clear()
    cleared.append("embedding_cache")
    
    document_cache.clear()
    cleared.append("document_cache")
    
    query_result_cache.clear()
    cleared.append("query_result_cache")
    
    logger.info(f"Cleared caches: {cleared}")
    
    return cleared