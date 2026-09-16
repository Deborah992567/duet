"""Friendship and friend request models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import FriendshipStatus
from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class FriendRequest(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "friend_requests"

    sender_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    recipient_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[FriendshipStatus] = mapped_column(
        Enum(FriendshipStatus, native_enum=False, length=16),
        default=FriendshipStatus.PENDING,
        nullable=False,
    )
    message: Mapped[str | None] = mapped_column(String(280), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_friend_requests_pair", "sender_id", "recipient_id", unique=True),
        Index("ix_friend_requests_recipient_status", "recipient_id", "status"),
    )


class Friendship(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    """An accepted, bidirectional connection between two users."""

    __tablename__ = "friendships"

    # Canonical ordering: user_a < user_b to prevent duplicates.
    user_a: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_b: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[FriendshipStatus] = mapped_column(
        Enum(FriendshipStatus, native_enum=False, length=16),
        default=FriendshipStatus.ACCEPTED,
        nullable=False,
    )
    removed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_friendships_pair", "user_a", "user_b", unique=True),
        Index("ix_friendships_status", "status"),
    )