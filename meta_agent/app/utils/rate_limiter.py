import time
from collections import defaultdict, deque
from fastapi import HTTPException, status
from app.utils.logger import logger


class RateLimiter:
    """Token bucket rate limiter"""
    
    def __init__(self, requests_per_minute: int = 10):
        self.rpm = requests_per_minute
        self.requests: defaultdict[str, deque] = defaultdict(deque)
    
    def check(self, user_id: str) -> bool:
        """Returns True if request is allowed, False if rate limited"""
        now = time.time()
        window_start = now - 60
        
        # Clean old requests
        while self.requests[user_id] and self.requests[user_id][0] < window_start:
            self.requests[user_id].popleft()
        
        if len(self.requests[user_id]) >= self.rpm:
            return False
        
        self.requests[user_id].append(now)
        return True
    
    def enforce(self, user_id: str):
        """Raises HTTPException if rate limited"""
        if not self.check(user_id):
            logger.warning(f"Rate limit exceeded for user {user_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.rpm} requests per minute."
            )


# Global instance
rate_limiter = RateLimiter(requests_per_minute=10)