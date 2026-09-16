"""User, profile, device/session, and blocked-user models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import (
    DevicePlatform,
    MAX_BIO_LENGTH,
    MAX_DISPLAY_NAME_LENGTH,
    MAX_USERNAME_LENGTH,
    UserStatus,
)
from app.db.session import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    pass


class User(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(
        String(MAX_USERNAME_LENGTH), unique=True, index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(
        String(191), unique=True, index=True, nullable=False
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False, length=16),
        default=UserStatus.ACTIVE,
        index=True,
        nullable=False,
    )
    # Streak behaviour preferences (user-controlled, no dark patterns).
    streak_notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    streak_reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    streak_freezes_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    streak_visible: Mapped[bool] = mapped_column(Boolean, default=True)

    # Privacy settings
    read_receipts_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    show_online_status: Mapped[bool] = mapped_column(Boolean, default=True)
    profile_visibility: Mapped[str] = mapped_column(  # everyone | friends | nobody
        String(16), default="everyone", nullable=False
    )

    # Push
    notification_preview_allowed: Mapped[bool] = mapped_column(Boolean, default=True)

    locale: Mapped[str] = mapped_column(String(8), default="en")
    theme: Mapped[str] = mapped_column(String(16), default="system")  # light|dark|system
    timezone: Mapped[str] = mapped_column(String(32), default="UTC")

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # One-time token support for password recovery / email verification
    reset_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_code_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    verification_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    profile: Mapped["UserProfile"] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    __table_args__ = (Index("ix_users_status_last_seen", "status", "last_seen_at"),)


class UserProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_profiles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(
        String(MAX_DISPLAY_NAME_LENGTH), nullable=False
    )
    bio: Mapped[str] = mapped_column(Text, default="", nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    avatar_thumb_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone_region: Mapped[str | None] = mapped_column(String(8), nullable=True)

    user: Mapped[User] = relationship(back_populates="profile")


class Device(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    """A signed-in device with an opaque refresh token + APNs token."""

    __tablename__ = "devices"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    platform: Mapped[DevicePlatform] = mapped_column(
        Enum(DevicePlatform, native_enum=False, length=16), default=DevicePlatform.IOS
    )
    device_name: Mapped[str] = mapped_column(String(255), default="iPhone")
    os_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    push_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    refresh_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BlockedUser(TimestampMixin, UUIDPrimaryKeyMixin, Base):
    __tablename__ = "blocked_users"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    blocked_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    __table_args__ = (
        Index("ix_blocked_pair", "user_id", "blocked_user_id", unique=True),
    )