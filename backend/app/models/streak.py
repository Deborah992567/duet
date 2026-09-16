"""Streak models.

A streak row exists per (user, peer, conversation) directed pair. The engine
derives current/longest from immutable `streak_events` (append-only log), so
re-computation is deterministic and auditable.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import BigIntPKMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Streak(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "streaks"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    peer_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    longest_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    prepared_at: Mapped[date | None] = mapped_column(Date, nullable=True)  # last qualifying day (index day)
    # Freeze/saver balance (user opt-in).
    freezes_available: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "peer_user_id", "conversation_id", name="uq_streak_triple"),
        Index("ix_streak_user_alive", "user_id", "prepared_at"),
    )


class StreakEvent(TimestampMixin, BigIntPKMixin, Base):
    """Append-only log of streak lifecycle events."""

    __tablename__ = "streak_events"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    peer_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(24), nullable=False)  # incremented|milestone|broken|freeze_used|recovered|freeze_granted
    day: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    streak_after: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta: Mapped[str | None] = mapped_column(String(512), nullable=True)

    __table_args__ = (Index("ix_streak_events_user_day", "user_id", "day"),)


class StreakDayQualification(TimestampMixin, BigIntPKMixin, Base):
    """One row per user-conversation-day that qualifies toward a streak.

    For a *direct* conversation, a day qualifies for the streak round only when
    BOTH participants sent at least one message that day. This table records the
    per-user qualification so the engine can join and decide deterministically.
    """

    __tablename__ = "streak_day_qualifications"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    peer_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    day: Mapped[date] = mapped_column(Date, nullable=False)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    first_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "conversation_id", "day", name="uq_qualification_ucd"),
        Index("ix_qualification_day", "day"),
        Index("ix_qualification_peer_day", "peer_user_id", "day"),
    )