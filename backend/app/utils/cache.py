"""
Redis cache utilities
"""

import json
import os
from datetime import timedelta
from typing import Any, Optional

from app.config import get_settings

# Check if Redis is available
REDIS_AVAILABLE = False
redis = None
ConnectionPool = None

try:
    import redis.asyncio as redis_module
    from redis.asyncio.connection import ConnectionPool as CP
    redis = redis_module
    ConnectionPool = CP
    REDIS_AVAILABLE = True
except ImportError:
    pass

def _get_settings():
    """Lazy settings loader"""
    return get_settings()

# Connection pool
_pool = None


async def get_redis_pool():
    """Get or create Redis connection pool"""
    global _pool
    if not REDIS_AVAILABLE:
        return None
    if _pool is None:
        settings = _get_settings()
        _pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=20,
            decode_responses=True,
        )
    return _pool


async def get_redis():
    """Get Redis client"""
    if not REDIS_AVAILABLE:
        return None
    pool = await get_redis_pool()
    if pool is None:
        return None
    return redis.Redis(connection_pool=pool)


async def close_redis():
    """Close Redis connections"""
    global _pool
    if _pool is not None and REDIS_AVAILABLE:
        await _pool.disconnect()
        _pool = None


class CacheService:
    """Cache service for LLM responses and other data"""

    def __init__(self, prefix: str = "llmscm"):
        self.prefix = prefix

    def _key(self, key: str) -> str:
        """Generate full cache key with prefix"""
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        client = await get_redis()
        if client is None:
            return None
        value = await client.get(self._key(key))
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache with optional TTL (seconds)"""
        client = await get_redis()
        if client is None:
            return False
        if ttl is None:
            settings = _get_settings()
            ttl = settings.REDIS_CACHE_TTL

        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        return await client.setex(self._key(key), ttl, value)

    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        client = await get_redis()
        if client is None:
            return False
        return await client.delete(self._key(key)) > 0

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        client = await get_redis()
        if client is None:
            return False
        return await client.exists(self._key(key)) > 0

    async def get_ttl(self, key: str) -> int:
        """Get remaining TTL for key"""
        client = await get_redis()
        if client is None:
            return -1
        return await client.ttl(self._key(key))

    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter"""
        client = await get_redis()
        if client is None:
            return 0
        return await client.incrby(self._key(key), amount)

    async def set_with_lock(
        self,
        key: str,
        value: Any,
        ttl: int,
        lock_ttl: int = 30
    ) -> bool:
        """Set value only if key doesn't exist (for distributed locking)"""
        client = await get_redis()
        if client is None:
            return False
        lock_key = f"{self._key(key)}:lock"

        # Try to acquire lock
        acquired = await client.set(lock_key, "1", ex=lock_ttl, nx=True)
        if not acquired:
            return False

        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            await client.setex(self._key(key), ttl, value)
            return True
        finally:
            await client.delete(lock_key)


# LLM Response cache
class LLMResponseCache(CacheService):
    """Specialized cache for LLM responses"""

    def __init__(self):
        super().__init__(prefix="llmscm:llm_response")

    async def get_response(self, cache_key: str) -> Optional[dict]:
        """Get cached LLM response"""
        return await self.get(cache_key)

    async def set_response(
        self,
        cache_key: str,
        response: dict,
        ttl: Optional[int] = None
    ) -> bool:
        """Cache LLM response"""
        return await self.set(cache_key, response, ttl)

    async def invalidate_for_prompt(self, prompt_hash: str) -> int:
        """Invalidate all cached responses for a prompt"""
        client = await get_redis()
        pattern = f"{self.prefix}:{prompt_hash}:*"
        keys = await client.keys(pattern)
        if keys:
            return await client.delete(*keys)
        return 0


# Rate limiting cache
class RateLimitCache(CacheService):
    """Rate limiting with sliding window"""

    def __init__(self):
        super().__init__(prefix="llmscm:ratelimit")

    async def check_rate_limit(
        self,
        identifier: str,
        limit: int,
        window_seconds: int
    ) -> tuple[bool, int]:
        """
        Check if rate limit is exceeded.
        Returns (is_allowed, remaining_requests)
        """
        client = await get_redis()
        if client is None:
            # No Redis, allow all requests
            return True, limit
        key = self._key(identifier)

        current = await client.get(key)
        if current is None:
            # First request in window
            await client.setex(key, window_seconds, 1)
            return True, limit - 1

        current_count = int(current)
        if current_count >= limit:
            return False, 0

        await client.incr(key)
        return True, limit - current_count - 1

    async def get_remaining(
        self,
        identifier: str,
        limit: int
    ) -> int:
        """Get remaining requests in current window"""
        client = await get_redis()
        if client is None:
            return limit
        key = self._key(identifier)
        current = await client.get(key)
        if current is None:
            return limit
        return max(0, limit - int(current))


# Initialize cache instances
cache = CacheService()
llm_cache = LLMResponseCache()
rate_limit = RateLimitCache()
