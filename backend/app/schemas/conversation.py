"""Conversation and membership schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import (
    MAX_GROUP_MEMBERS,
    MAX_GROUP_NAME_LENGTH,
    ConversationType,
    MemberRole,
)
from app.schemas.user import UserPublic


class CreateDirectConversationPayload(BaseModel):
    user_id: str


class CreateGroupPayload(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_GROUP_NAME_LENGTH)
    description: str | None = Field(default=None, max_length=500)
    member_ids: list[str] = Field(default_factory=list, max_length=MAX_GROUP_MEMBERS - 1)
    admin_ids: list[str] = Field(default_factory=list)


class UpdateGroupPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=MAX_GROUP_NAME_LENGTH)
    description: str | None = Field(default=None, max_length=500)
    photo_url: str | None = None
    members_can_add: bool | None = None
    members_can_edit_group_info: bool | None = None
    admin_only_messaging: bool | None = None


class AddMembersPayload(BaseModel):
    user_ids: list[str] = Field(min_length=1, max_length=50)
    as_admins: bool = False


class RemoveMemberPayload(BaseModel):
    user_id: str


class PromoteMemberPayload(BaseModel):
    user_id: str


class DemoteMemberPayload(BaseModel):
    user_id: str


class ConversationMemberPublic(BaseModel):
    user: UserPublic
    role: MemberRole
    joined_at: datetime
    is_muted: bool = False
    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: str
    type: ConversationType
    name: str | None = None
    photo_url: str | None = None
    last_message_preview: str | None = None
    last_message_at: datetime | None = None
    last_message_sender_id: str | None = None
    unread_count: int = 0
    is_pinned: bool = False
    is_muted: bool = False
    member_count: int = 0
    peer: UserPublic | None = None  # for direct conversations
    current_streak: int = 0
    streak_alive: bool = False
    colors: list[str] = Field(default_factory=list)
    model_config = {"from_attributes": True}


class ConversationDetail(ConversationSummary):
    members: list[ConversationMemberPublic] = Field(default_factory=list)
    role: MemberRole = MemberRole.MEMBER
    members_can_add: bool = True
    members_can_edit_group_info: bool = True
    admin_only_messaging: bool = False


class ConversationList(BaseModel):
    items: list[ConversationSummary]
    has_more: bool = False
    next_cursor: str | None = None


class MarkReadPayload(BaseModel):
    up_to_message_id: str | None = None
    all: bool = False


class MutePayload(BaseModel):
    muted: bool = True


class PinPayload(BaseModel):
    pinned: bool = True
    conversation_id: str | None = None