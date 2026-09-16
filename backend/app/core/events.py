"""Real-time event contracts shared by the WebSocket layer.

Events flow from server to clients as JSON envelopes:

    {"v": 1, "id": "<uuid>", "type": "message.created", "conversation_id": "...", "data": {...}}

Every payload is validated by a Pydantic model so producers cannot emit
malformed events. Event names are stable and will be versioned by bumping `v`
and/or adding suffixed types (e.g. ``message.created.v2``) rather than breaking
existing consumers.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType:
    MESSAGE_CREATED = "message.created"
    MESSAGE_UPDATED = "message.updated"
    MESSAGE_DELETED = "message.deleted"
    MESSAGE_DELIVERED = "message.delivered"
    MESSAGE_READ = "message.read"
    REACTION_CREATED = "reaction.created"
    REACTION_REMOVED = "reaction.removed"
    TYPING_STARTED = "typing.started"
    TYPING_STOPPED = "typing.stopped"
    PRESENCE_CHANGED = "presence.changed"
    CONVERSATION_UPDATED = "conversation.updated"
    CONVERSATION_MEMBERSHIP_CHANGED = "conversation.membership.changed"
    FRIEND_REQUEST_RECEIVED = "friend.request.received"
    FRIEND_REQUEST_RESOLVED = "friend.request.resolved"
    FRIENDSHIP_REMOVED = "friendship.removed"
    CALL_RECEIVED = "call.received"
    CALL_UPDATED = "call.updated"
    STREAK_UPDATED = "streak.updated"
    STREAK_MILESTONE = "streak.milestone"
    STREAK_REMINDER = "streak.reminder"
    NOTIFICATION_CREATED = "notification.created"
    UNREAD_COUNT_UPDATED = "unread_count.updated"
    SESSION_REVOKED = "session.revoked"


class Envelope(BaseModel):
    v: int = 1
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    data: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Payload schemas for the most important events.
# ---------------------------------------------------------------------------


class MessageCreatedPayload(BaseModel):
    message: dict[str, Any]
    # provider echoes the client's temporary id so the sender can correlate.
    client_id: Optional[str] = None


class MessageUpdatedPayload(BaseModel):
    message: dict[str, Any]


class MessageDeletedPayload(BaseModel):
    message_id: str
    delete_for: str
    deleted_content: Optional[str] = None


class ReceiptPayload(BaseModel):
    conversation_id: str
    message_id: str
    user_id: str
    at: str


class PresencePayload(BaseModel):
    user_id: str
    status: str
    last_seen_at: Optional[str] = None


class TypingPayload(BaseModel):
    conversation_id: str
    user_id: str
    at: str


class ReactionPayload(BaseModel):
    conversation_id: str
    message_id: str
    user_id: str
    emoji: str
    reaction_id: Optional[str] = None
    removed: bool = False


class StreakUpdatedPayload(BaseModel):
    user_id: str
    peer_user_id: str
    conversation_id: str
    current_streak: int
    longest_streak: int
    alive: bool
    last_activity_day: Optional[str] = None


class StreakMilestonePayload(BaseModel):
    user_id: str
    peer_user_id: str
    conversation_id: str
    milestone: int
    current_streak: int
    longest_streak: int


class CallPayload(BaseModel):
    call: dict[str, Any]