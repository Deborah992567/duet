"""Async Redis client provisioning.

A lazy singleton; tests can swap in fakeredis via `set_current_redis(None)`.
"""

from __future__ import annotations

from typing import Optional

from redis.asyncio import Redis

from app.core.config import settings

_current: Optional[Redis] = None
_owns_connection = False


def get_redis() -> Optional[Redis]:
    """Return the shared Redis client or None when disabled/unavailable."""
    global _current, _owns_connection
    if _current is None and settings.environment != "test":
        try:
            _current = Redis.from_url(settings.redis_url, decode_responses=True)
            _owns_connection = True
        except Exception:  # pragma: no cover
            _current = None
    return _current


def set_current_redis(redis: Optional[Redis]) -> None:
    global _current, _owns_connection
    _current = redis
    _owns_connection = False


async def close_redis() -> None:
    global _current, _owns_connection
    if _current is not None and _owns_connection:  # pragma: no cover
        await _current.aclose()
    _current = None
    _owns_connection = False