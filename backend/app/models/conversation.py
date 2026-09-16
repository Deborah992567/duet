"""Conversation and conversation member models.

A conversation is a first-class aggregate: it has its own id, metadata, and a
membership table carrying per-member roles and per-member visibility flags
(needed for scalable groups rather than a simple list of users).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import ConversationType, MemberRole
from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Conversation(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "conversations"

    type: Mapped[ConversationType] = mapped_column(
        Enum(ConversationType, native_enum=False, length=16), nullable=False, index=True
    )

    # Group metadata (null for direct conversations)
    name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # For direct conversations, the canonical string `user_a:user_b` (sorted ids)
    # allows a unique constraint and fast lookups.
    direct_key: Mapped[str | None] = mapped_column(String(65), unique=True, index=True, nullable=True)

    # Group settings
    members_can_add: Mapped[bool] = mapped_column(Boolean, default=True)
    members_can_edit_group_info: Mapped[bool] = mapped_column(Boolean, default=True)
    admin_only_messaging: Mapped[bool] = mapped_column(Boolean, default=False)
    max_members: Mapped[int] = mapped_column(Integer, default=512)

    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_conversations_updated", "updated_at"),)


class ConversationMember(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "conversation_members"

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole, native_enum=False, length=16),
        default=MemberRole.MEMBER,
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    last_read_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id"), nullable=True
    )
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)  # hide conversation
    nickname: Mapped[str | None] = mapped_column(String(60), nullable=True)

    __table_args__ = (
        UniqueConstraint("conversation_id", "user_id", name="uq_member_conversation_user"),
        Index("ix_members_user", "user_id"),
    )