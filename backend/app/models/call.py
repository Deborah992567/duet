"""Call and call participant models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import (
    CallDirection,
    CallKind,
    CallState,
)
from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Call(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "calls"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    initiator_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[CallKind] = mapped_column(
        Enum(CallKind, native_enum=False, length=16), nullable=False
    )
    direction: Mapped[CallDirection] = mapped_column(
        Enum(CallDirection, native_enum=False, length=16), nullable=False
    )
    state: Mapped[CallState] = mapped_column(
        Enum(CallState, native_enum=False, length=16), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    peer_user_id: Mapped[str] = mapped_column(index=True, nullable=False)

    __table_args__ = (Index("ix_calls_user_history", "initiator_id", "created_at"),)


class CallParticipant(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "call_participants"

    call_id: Mapped[str] = mapped_column(
        ForeignKey("calls.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), default="participant")
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (Index("ix_call_participants_user", "user_id"),)