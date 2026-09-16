"""Authentication primitives: password hashing, JWT issuing/verification, tokens.

Uses `bcrypt` directly (passlib 1.7.4 is incompatible with modern bcrypt 4.x)
and `python-jose` for symmetric HS256 access tokens. Device/refresh tokens are
opaque random strings stored server-side in the `devices` table.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt

from app.core.config import settings
from app.core.errors import UnauthorizedError

import bcrypt

_ACCESS_TOKEN_ISSUER = "envychat"


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=settings.bcrypt_rounds)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def generate_opaque_token(length: int = 32) -> str:
    """Cryptographically secure random token (device / refresh tokens)."""
    return secrets.token_urlsafe(length)


def issue_access_token(subject: str, claims: Optional[dict[str, Any]] = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "iss": _ACCESS_TOKEN_ISSUER,
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm], issuer=_ACCESS_TOKEN_ISSUER
        )
    except JWTError as exc:
        raise UnauthorizedError(code="invalid_token", message="Your session is invalid. Please sign in again.") from exc
    return payload