"""Streak schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.schemas.user import UserPublic


class StreakPublic(BaseModel):
    user_id: str
    peer_user_id: str
    conversation_id: str
    current_streak: int
    longest_streak: int
    longest_start_date: date | None = None
    prepared_at: date | None = None
    alive: bool = True
    day_remaining_seconds: int = 0
    milestones_reached: list[int] = Field(default_factory=list, description="sorted ascending")
    closest_milestone: int | None = None
    freezes_available: int = 0
    model_config = {"from_attributes": True}


class StreakSummary(BaseModel):
    """Compact form for conversation list / profile."""

    user_id: str
    peer_user_id: str
    conversation_id: str
    current_streak: int
    longest_streak: int
    alive: bool
    last_activity_day: date | None = None
    peer: UserPublic | None = None


class StreakList(BaseModel):
    items: list[StreakSummary]
    has_more: bool = False
    next_cursor: str | None = None


class StreakEventOut(BaseModel):
    event_type: str
    day: date
    streak_after: int
    meta: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class StreakHistory(BaseModel):
    items: list[StreakEventOut]
    has_more: bool = False


class StreakSettingsPayload(BaseModel):
    notifications_enabled: bool | None = None
    reminders_enabled: bool | None = None
    freezes_enabled: bool | None = None
    visible: bool | None = None


class StreakReminderIn(BaseModel):
    """Payload for a triggered reminder; server-side only."""
    user_id: str
    conversation_id: str
    message: str | None = None