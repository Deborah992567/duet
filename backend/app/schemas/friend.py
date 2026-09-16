"""Friendship / friend request schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import FriendshipStatus
from app.schemas.user import UserPublic


class SendFriendRequestPayload(BaseModel):
    user_id: str
    message: str | None = Field(default=None, max_length=280)


class FriendRequestPublic(BaseModel):
    id: str
    sender_id: str
    recipient_id: str
    status: FriendshipStatus
    message: str | None = None
    created_at: datetime
    sender: UserPublic | None = None
    recipient: UserPublic | None = None
    model_config = {"from_attributes": True}


class RespondFriendRequestPayload(BaseModel):
    accept: bool


class RemoveFriendPayload(BaseModel):
    user_id: str


class FriendSummary(BaseModel):
    friendship_id: str
    user: UserPublic
    created_at: datetime


class FriendList(BaseModel):
    items: list[FriendSummary]
    has_more: bool = False
    next_cursor: str | None = None


class MutualConnection(BaseModel):
    user: UserPublic
    mutual_count: int


class BlockUserPayload(BaseModel):
    user_id: str
    also_remove_as_friend: bool = True


class ReportUserPayload(BaseModel):
    user_id: str | None = None
    message_id: str | None = None
    reason: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)