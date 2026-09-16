"""User/profile request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, HttpUrl, field_validator, Field

from app.core.constants import (
    MAX_BIO_LENGTH,
    MAX_DISPLAY_NAME_LENGTH,
    MAX_USERNAME_LENGTH,
    UserStatus,
)


class UserPublic(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None = None
    bio: str = ""
    status: UserStatus = UserStatus.ACTIVE
    is_friend: bool = False
    is_blocked: bool = False
    online: bool = False
    last_seen_at: datetime | None = None
    streak_visible: bool = True
    model_config = {"from_attributes": True}


class UserMe(UserPublic):
    email: str
    email_verified: bool
    phone: str | None = None
    streak_notifications_enabled: bool
    streak_reminders_enabled: bool
    streak_freezes_enabled: bool
    streak_visible: bool
    read_receipts_enabled: bool
    show_online_status: bool
    profile_visibility: str
    theme: str
    locale: str
    timezone: str
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)
    bio: str | None = Field(default=None, max_length=MAX_BIO_LENGTH)
    username: str | None = Field(default=None, min_length=3, max_length=MAX_USERNAME_LENGTH)
    avatar_url: HttpUrl | None = None
    phone: str | None = Field(default=None, max_length=32)
    theme: str | None = Field(default=None, pattern="^(light|dark|system)$")
    locale: str | None = Field(default=None, max_length=8)
    timezone: str | None = Field(default=None, max_length=32)

    @field_validator("username")
    @classmethod
    def _username_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import re

        if not re.match(r"^[a-z0-9_]{3,20}$", v):
            raise ValueError("Invalid username.")
        return v


class UserSearchResult(BaseModel):
    items: list[UserPublic]
    has_more: bool = False
    next_cursor: str | None = None


class DevicePublic(BaseModel):
    id: str
    device_name: str
    platform: str
    os_version: str | None = None
    app_version: str | None = None
    last_used_at: datetime | None = None
    is_current: bool = False
    created_at: datetime
    model_config = {"from_attributes": True}


class BlockedUserPublic(BaseModel):
    id: str
    blocked_at: datetime
    user: UserPublic | None = None


class PrivacySettingsPayload(BaseModel):
    read_receipts_enabled: bool | None = None
    show_online_status: bool | None = None
    profile_visibility: str | None = Field(default=None, pattern="^(everyone|friends|nobody)$")
    notification_preview_allowed: bool | None = None


class DeleteAccountRequest(BaseModel):
    password: str
    confirmation: str  # must equal "DELETE"