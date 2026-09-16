"""Service layer base.

Services own business rules, orchestrate repositories, and emit real-time
events through the injected connection manager. They never import FastAPI
routing concerns; routers translate HTTP <-> service calls.
"""

from __future__ import annotations

from typing import Optional

from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.core.rate_limit import RateLimiter
from app.ws.manager import WSConnectionManager


class Service:
    def __init__(
        self,
        db: Session,
        *,
        redis: Optional[Redis] = None,
        ws: Optional[WSConnectionManager] = None,
    ) -> None:
        self.db = db
        self.redis = redis
        self.ws = ws or WSConnectionManager(redis=redis)
        self.rate_limiter = RateLimiter(redis=redis)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def flush(self) -> None:
        self.db.flush()