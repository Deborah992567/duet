"""Report and settings schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.constants import ReportKind, ReportStatus


class CreateReportPayload(BaseModel):
    kind: ReportKind
    target_user_id: str | None = None
    message_id: str | None = None
    conversation_id: str | None = None
    reason: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)


class ReportOut(BaseModel):
    id: str
    kind: ReportKind
    reason: str
    status: ReportStatus
    created_at: object | None = None
    model_config = {"from_attributes": True}


class ThemeUpdatePayload(BaseModel):
    theme: str = Field(pattern="^(light|dark|system)$")


class PrivacySettingsPayload(BaseModel):
    read_receipts_enabled: bool | None = None
    show_online_status: bool | None = None
    profile_visibility: str | None = Field(default=None, pattern="^(everyone|friends|nobody)$")
    notification_preview_allowed: bool | None = None


class AppVersionResponse(BaseModel):
    version: str
    minimum_ios_version: str
    force_update: bool = False
    update_url: str | None = None