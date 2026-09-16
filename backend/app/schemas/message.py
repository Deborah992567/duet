"""Message, reaction, send/query schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import (
    MAX_MESSAGE_ATTACHMENTS,
    MAX_MESSAGE_LENGTH,
    MessageKind,
    MessageServerStatus,
    ReactionType,
)
from app.schemas.media import AttachmentOut


class AttachmentDraft(BaseModel):
    # Uploaded before the message is created (media endpoint returns upload_id).
    upload_id: str
    kind: str
    file_name: str | None = None
    size_bytes: int | None = None
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    waveform: list[int] | None = None


class SendMessagePayload(BaseModel):
    conversation_id: str | None = None  # path is authoritative; body optional
    kind: MessageKind = MessageKind.TEXT
    body: str | None = Field(default=None, max_length=MAX_MESSAGE_LENGTH)
    client_id: str | None = Field(default=None, max_length=64)
    client_sequence: int = 0
    reply_to_message_id: str | None = None
    attachments: list[AttachmentDraft] = Field(
        default_factory=list, max_length=MAX_MESSAGE_ATTACHMENTS
    )
    metadata: dict | None = None


class EditMessagePayload(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)


class DeleteMessagePayload(BaseModel):
    delete_for: str = "me"  # me | everyone


class ReactPayload(BaseModel):
    emoji: str = Field(min_length=1, max_length=16)
    reaction_type: ReactionType = ReactionType.CUSTOM


class ReactionOut(BaseModel):
    id: str
    user_id: str
    emoji: str
    reaction_type: ReactionType
    created_at: datetime
    model_config = {"from_attributes": True}


class ForwardMessagePayload(BaseModel):
    message_id: str
    to_conversation_ids: list[str] = Field(min_length=1, max_length=20)


class MessageOut(BaseModel):
    id: str
    server_id: int
    conversation_id: str
    sender_id: str
    kind: MessageKind
    body: str | None = None
    client_id: str | None = None
    reply_to_message_id: str | None = None
    attachments: list[AttachmentOut] = Field(default_factory=list)
    reactions: list[ReactionOut] = Field(default_factory=list)
    sent_at: datetime
    status: MessageServerStatus = MessageServerStatus.SENT
    delivery_statuses: dict[str, str] = Field(default_factory=dict)
    is_edited: bool = False
    deleted_for_me: bool = False
    model_config = {"from_attributes": True}


class MessageList(BaseModel):
    items: list[MessageOut]
    has_more: bool = False
    next_cursor: str | None = None


class SendMessageResult(BaseModel):
    message: MessageOut
    client_id: str | None = None


class SearchMessagesPayload(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    conversation_id: str | None = None
    cursor: str | None = None
    limit: int = Field(default=30, ge=1, le=100)