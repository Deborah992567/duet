"""Reusable SQLAlchemy model mixins."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.orm import Mapped, mapped_column

# Use a MariaDB-native CHAR(32) for UUIDs; `str` fallback keeps SQLite tests happy
# (SQLAlchemy renders CHAR as TEXT-equivalent, still indexable).


def uuid_string() -> str:
    return uuid.uuid4().hex


class UUIDPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(CHAR(32), primary_key=True, default=uuid_string)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BigIntPKMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)