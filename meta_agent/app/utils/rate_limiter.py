"""
Redis-based distributed sliding window rate limiter.

Algorithm: sorted set per user keyed by timestamp.
  1. ZREMRANGEBYSCORE  — evict entries older than the window
  2. ZADD              — record current request (score = timestamp ms)
  3. ZCARD             — count requests in window
  4. EXPIRE            — auto-cleanup if user goes idle
All four ops run inside a Redis pipeline (single round-trip).
"""

import time
import uuid
from typing import Optional

from fastapi import HTTPException, status

from app.core.cache import redis_client
from app.utils.logger import logger

_KEY_PREFIX = "rate_limit"
_DEFAULT_RPM = 10
_WINDOW_SECONDS = 60


class RateLimiter:
    def __init__(self, requests_per_minute: int = _DEFAULT_RPM):
        self.rpm = requests_per_minute

    def _redis_available(self) -> bool:
        return redis_client is not None

    def check(self, identifier: str) -> bool:
        """Returns True if request is allowed, False if rate limited."""
        if not self._redis_available():
            logger.warning("Redis unavailable — rate limiter failing open")
            return True

        key = f"{_KEY_PREFIX}:{identifier}"
        now_ms = time.time() * 1000
        window_start_ms = now_ms - (_WINDOW_SECONDS * 1000)
        # Unique member so concurrent requests never overwrite each other
        member = f"{now_ms}:{uuid.uuid4().hex[:8]}"

        try:
            pipe = redis_client.pipeline(transaction=True)
            pipe.zremrangebyscore(key, "-inf", window_start_ms)
            pipe.zadd(key, {member: now_ms})
            pipe.zcard(key)
            pipe.expire(key, _WINDOW_SECONDS + 1)
            results = pipe.execute()

            request_count: int = results[2]

            if request_count > self.rpm:
                # Roll back the entry we just added
                redis_client.zrem(key, member)
                logger.warning(
                    "Rate limit hit for %s (%d/%d in window)",
                    identifier, request_count, self.rpm,
                )
                return False

            return True
        except Exception as e:
            logger.error("Rate limiter Redis error: %s — failing open", e)
            return True

    def enforce(self, identifier: str) -> None:
        """Raises HTTP 429 if rate limited."""
        if not self.check(identifier):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {self.rpm} requests per minute.",
            )

    def remaining(self, identifier: str) -> Optional[int]:
        """Returns how many requests remain in the current window, or None on error."""
        if not self._redis_available():
            return None
        try:
            key = f"{_KEY_PREFIX}:{identifier}"
            now_ms = time.time() * 1000
            window_start_ms = now_ms - (_WINDOW_SECONDS * 1000)
            redis_client.zremrangebyscore(key, "-inf", window_start_ms)
            count = redis_client.zcard(key)
            return max(0, self.rpm - count)
        except Exception:
            return None


# Global instance — drop-in replacement for the old in-memory limiter
rate_limiter = RateLimiter(requests_per_minute=_DEFAULT_RPM)
