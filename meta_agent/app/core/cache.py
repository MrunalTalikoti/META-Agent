import json
from typing import Any, Optional

import redis

from app.core.config import settings
from app.utils.logger import logger

# ── Client ────────────────────────────────────────────────────────────────────
try:
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    redis_client.ping()
    logger.info("✓ Redis connected")
except Exception as e:
    logger.warning(f"Redis unavailable ({e}) — caching disabled")
    redis_client = None


# ── Cache Service ─────────────────────────────────────────────────────────────
class CacheService:
    @staticmethod
    def _available() -> bool:
        return redis_client is not None

    @staticmethod
    def set(key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """Store a value. Returns True on success."""
        if not CacheService._available():
            return False
        try:
            redis_client.setex(key, ttl_seconds, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"Cache set failed for key={key}: {e}")
            return False

    @staticmethod
    def get(key: str) -> Optional[Any]:
        """Retrieve a value. Returns None on miss or error."""
        if not CacheService._available():
            return None
        try:
            raw = redis_client.get(key)
            return json.loads(raw) if raw else None
        except Exception as e:
            logger.error(f"Cache get failed for key={key}: {e}")
            return None

    @staticmethod
    def delete(key: str) -> bool:
        if not CacheService._available():
            return False
        try:
            redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete failed: {e}")
            return False

    # ── Convenience helpers ───────────────────────────────────────────────────

    @staticmethod
    def cache_project(project_id: int, data: dict, ttl: int = 300):
        CacheService.set(f"project:{project_id}", data, ttl)

    @staticmethod
    def get_project(project_id: int) -> Optional[dict]:
        return CacheService.get(f"project:{project_id}")

    @staticmethod
    def invalidate_project(project_id: int):
        CacheService.delete(f"project:{project_id}")

    @staticmethod
    def cache_llm_response(cache_key: str, response: dict, ttl: int = 86400):
        """Cache expensive LLM responses for 24 hours."""
        CacheService.set(f"llm:{cache_key}", response, ttl)

    @staticmethod
    def get_llm_response(cache_key: str) -> Optional[dict]:
        return CacheService.get(f"llm:{cache_key}")