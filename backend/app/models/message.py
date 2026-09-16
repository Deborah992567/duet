"""Message, reaction, attachment, receipt, edit, and deletion models.

Messages are versioned via `message_edits`, soft-deleted via `message_deletions`
(to support future sync and "delete for everyone" semantics), and tracked with
per-member receipts for delivered/read states.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    MAX_MESSAGE_LENGTH,
    MessageKind,
    ReactionType,
)
from app.db.session import Base
from app.models.mixins import BigIntPKMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from sqlalchemy.ext.asmapping import _T  # noqa: F401


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"

    # Big-picture ordering key (monotonic per conversation).
    server_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)

    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sender_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[MessageKind] = mapped_column(
        Enum(MessageKind, native_enum=False, length=16), nullable=False
    )
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    reply_to_message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id"), nullable=True
    )

    # Delivery ordering per sender (client clock, used to render correctly).
    client_sequence: Mapped[int] = mapped_column(BigInteger, default=0)

    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)

    # Simple foreign key to the sender's streak day marker is intentionally
    # avoided; streaks are derived in the service layer.
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    attachments: Mapped[list["MessageAttachment"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )
    reactions: Mapped[list["MessageReaction"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_messages_conv_server", "conversation_id", "server_id"),
        Index("ix_messages_sender_seq", "sender_id", "client_sequence"),
        UniqueConstraint("conversation_id", "server_id", name="uq_message_conv_server"),
    )


class MessageAttachment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "message_attachments"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # image|video|voice|file|gif|sticker
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    thumb_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    waveform: Mapped[list | None] = mapped_column(JSON, nullable=True)  # voice message peaks
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    message: Mapped[Message] = relationship(back_populates="attachments")


class MessageReaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "message_reactions"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    emoji: Mapped[str] = mapped_column(String(16), nullable=False)
    reaction_type: Mapped[ReactionType] = mapped_column(
        Enum(ReactionType, native_enum=False, length=16), nullable=False
    )

    message: Mapped[Message] = relationship(back_populates="reactions")

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", "emoji", name="uq_reaction_message_user_emoji"),
    )


class MessageReceipt(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-member delivery/read state."""

    __tablename__ = "message_receipts"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_receipt_message_user"),
        Index("ix_receipts_conversation_user", "conversation_id", "user_id", "read_at"),
    )


class MessageEdit(TimestampMixin, BigIntPKMixin, Base):
    __tablename__ = "message_edits"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    editor_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    previous_body: Mapped[str] = mapped_column(Text, nullable=False)
    edited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MessageDeletion(TimestampMixin, BigIntPKMixin, Base):
    __tablename__ = "message_deletions"

    message_id: Mapped[str] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    deleted_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    delete_for: Mapped[str] = mapped_column(String(16), nullable=False)  # me | everyone
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)