"""FastAPI dependency layer: authentication and service wiring.

Services are *not* singletons; each request builds one fresh service instance.
Injecting dependencies (db, redis, ws manager) keeps route handlers thin and
testable.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import Depends, Header, Query, Request, WebSocket
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.errors import UnauthorizedError
from app.core.redis_client import get_redis
from app.db.session import get_db
from app.models.user import User, UserStatus
from app.repositories.user_repo import UserRepository
from app.ws.manager import WSConnectionManager

bearer_scheme = HTTPBearer(auto_error=False)

_ws_manager: Optional[WSConnectionManager] = None


def get_ws_manager() -> WSConnectionManager:
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WSConnectionManager(redis=get_redis())
    return _ws_manager


def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None:
        raise UnauthorizedError("Authentication required.", code="missing_token")
    payload = security.decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token.", code="bad_token")
    user = UserRepository(db).get(user_id)
    if user is None or user.status not in (UserStatus.ACTIVE,):
        raise UnauthorizedError("This account is no longer active.", code="account_inactive")
    request.state.device_id = payload.get("dev")
    return user


async def get_current_user_ws(websocket: WebSocket, token: str = "") -> User:
    """Authenticate a WebSocket handshake via the access token (query param).

    Called directly from the websocket endpoint (FastAPI does not inject deps
    there), so the caller must pass the token from ``websocket.query_params``.
    """
    if not token:
        raise UnauthorizedError("Missing websocket token.", code="missing_ws_token")
    payload = security.decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token.", code="bad_ws_token")
    # A short-lived DB check keeps revoked sessions out of the socket pool.
    session_factory = websocket.app.state.session_factory
    db = session_factory()
    try:
        user = UserRepository(db).get(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise UnauthorizedError("Account inactive.", code="account_inactive")
        return user
    finally:
        db.close()


CurrentUser = Annotated[User, Depends(get_current_user)]
SessionDep = Annotated[Session, Depends(get_db)]