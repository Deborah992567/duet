"""Notification schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import NotificationKind


class NotificationOut(BaseModel):
    id: int
    kind: NotificationKind
    title: str
    body: str | None = None
    data: dict | None = None
    read_at: datetime | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class NotificationList(BaseModel):
    items: list[NotificationOut]
    has_more: bool = False
    next_cursor: str | None = None


class NotificationPreferencesOut(BaseModel):
    messages_enabled: bool
    groups_enabled: bool
    calls_enabled: bool
    streak_notifications: bool
    streak_reminders: bool
    friend_requests: bool
    security_alerts: bool
    show_preview: bool
    quiet_hours_enabled: bool
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    model_config = {"from_attributes": True}


class UpdateNotificationPreferencesPayload(BaseModel):
    messages_enabled: bool | None = None
    groups_enabled: bool | None = None
    calls_enabled: bool | None = None
    streak_notifications: bool | None = None
    streak_reminders: bool | None = None
    friend_requests: bool | None = None
    security_alerts: bool | None = None
    show_preview: bool | None = None
    quiet_hours_enabled: bool | None = None
    quiet_hours_start: str | None = Field(default=None, max_length=5)
    quiet_hours_end: str | None = Field(default=None, max_length=5)


class PushTokenPayload(BaseModel):
    device_id: str
    push_token: str = Field(min_length=10, max_length=512)