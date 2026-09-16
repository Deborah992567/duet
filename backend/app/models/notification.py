"""Notification and per-channel notification preference models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import NotificationKind
from app.db.session import Base
from app.models.mixins import BigIntPKMixin, TimestampMixin, UUIDPrimaryKeyMixin


class Notification(TimestampMixin, BigIntPKMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    kind: Mapped[NotificationKind] = mapped_column(
        Enum(NotificationKind, native_enum=False, length=32), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_via_apns: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)


class NotificationPreference(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    messages_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    groups_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    calls_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    streak_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    streak_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    friend_requests: Mapped[bool] = mapped_column(Boolean, default=True)
    security_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    show_preview: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5), nullable=True)