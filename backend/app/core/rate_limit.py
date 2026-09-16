"""Redis-backed rate limiting.

Fixed-window counter per (bucket, key). When Redis is unavailable it fails
open rather than taking the service down; production deploys configure a
highly-available Redis and rely on it.
"""

from __future__ import annotations

from typing import Optional

from redis.asyncio import Redis

from app.core.errors import TooManyRequestsError
from app.core.logging import get_logger

logger = get_logger(__name__)

_PREFIX = "rl"


class RateLimiter:
    def __init__(self, redis: Optional[Redis] = None) -> None:
        self._redis = redis

    @property
    def _live(self) -> bool:
        return self._redis is not None

    async def hit(
        self,
        bucket: str,
        key: str,
        limit: int,
        window_seconds: int = 60,
    ) -> None:
        """Record (or reject) one request."""
        if not self._live:
            return
        redis_key = f"{_PREFIX}:{bucket}:{key}"
        window = int(window_seconds)
        try:
            pipe = self._redis.pipeline(transaction=True)
            pipe.incr(redis_key)
            pipe.expire(redis_key, window)
            pipe.touch(redis_key)
            count, _ttl = await pipe.execute()
        except Exception:  # pragma: no cover - Redis outage
            logger.warning("rate limiter unavailable; failing open")
            return
        if count > limit:
            raise TooManyRequestsError()

    async def clear(self, bucket: str, key: str) -> None:
        if not self._live:
            return
        try:
            await self._redis.delete(f"{_PREFIX}:{bucket}:{key}")
        except Exception:  # pragma: no cover
            logger.warning("rate limiter clear failed")