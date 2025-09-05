from typing import Optional, Dict
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging

logger = logging.getLogger(__name__)

# Optional security bearer
security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Optional[Dict]:
    """Get current user from token (optional)"""
    if not credentials:
        return None
    
    # In production, validate JWT token here
    # For now, just return a dummy user
    return {
        "user_id": "anonymous",
        "permissions": ["read"]
    }

async def require_admin(
    user: Optional[Dict] = Depends(get_current_user)
) -> Dict:
    """Require admin permissions"""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    if "admin" not in user.get("permissions", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin permissions required"
        )
    
    return user

class RateLimiter:
    """Simple rate limiter"""
    
    def __init__(self, calls: int = 10, period: int = 60):
        self.calls = calls
        self.period = period
        self.cache = {}
    
    async def __call__(self, user: Optional[Dict] = Depends(get_current_user)):
        """Check rate limit"""
        import time
        
        user_id = user["user_id"] if user else "anonymous"
        now = time.time()
        
        if user_id not in self.cache:
            self.cache[user_id] = []
        
        # Remove old entries
        self.cache[user_id] = [
            t for t in self.cache[user_id] 
            if now - t < self.period
        ]
        
        # Check limit
        if len(self.cache[user_id]) >= self.calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {self.calls} calls per {self.period} seconds"
            )
        
        # Add current call
        self.cache[user_id].append(now)
        
        return True

# Create rate limiters with different limits
query_rate_limiter = RateLimiter(calls=30, period=60)
upload_rate_limiter = RateLimiter(calls=10, period=60)