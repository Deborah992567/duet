"""Authentication service: register, login, tokens, sessions, recovery."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.constants import DevicePlatform, UserStatus
from app.core.errors import (
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationAppError,
)
from app.models.user import Device, User
from app.repositories.user_repo import DeviceRepository, UserRepository
from app.schemas.auth import AuthResponse, DeviceInfo, TokenPair
from app.schemas.user import DevicePublic, UserMe
from app.services.base import Service


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(("ec:" + token).encode()).hexdigest()


def hash_verification(code: str) -> str:
    return hashlib.sha256(("verify:" + code).encode()).hexdigest()


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _user_to_me(user: User) -> UserMe:
    return UserMe(
        id=user.id,
        username=user.username,
        display_name=user.profile.display_name if user.profile else user.username,
        avatar_url=user.profile.avatar_url if user.profile else None,
        bio=user.profile.bio if user.profile else "",
        status=user.status,
        is_friend=False,
        is_blocked=False,
        online=False,
        email=user.email,
        email_verified=user.email_verified,
        phone=user.profile.phone if user.profile else None,
        streak_notifications_enabled=user.streak_notifications_enabled,
        streak_reminders_enabled=user.streak_reminders_enabled,
        streak_freezes_enabled=user.streak_freezes_enabled,
        streak_visible=user.streak_visible,
        read_receipts_enabled=user.read_receipts_enabled,
        show_online_status=user.show_online_status,
        profile_visibility=user.profile_visibility,
        theme=user.theme,
        locale=user.locale,
        timezone=user.timezone,
        created_at=user.created_at,
    )


class AuthService(Service):
    def __init__(self, db: Session, **kwargs):
        super().__init__(db, **kwargs)
        self.users = UserRepository(db)
        self.devices = DeviceRepository(db)

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    async def register(self, *, email: str, username: str, password: str, display_name: str, device: DeviceInfo) -> AuthResponse:
        if self.users.by_email(email):
            raise ConflictError("An account with this email already exists.", code="email_taken")
        if self.users.by_username(username):
            raise ConflictError("That username is already taken.", code="username_taken")

        user = User(
            username=username,
            email=email,
            password_hash=security.hash_password(password),
        )
        self.users.add(user)
        self.flush()
        self.users.create_profile(user.id, display_name)

        token_pair, device_id = await self._create_device(user.id, device)
        self.commit()
        return AuthResponse(tokens=token_pair, user=_user_to_me(user), registered=True)

    # ------------------------------------------------------------------ #
    # Login / refresh / logout
    # ------------------------------------------------------------------ #

    async def login(self, *, identifier: str, password: str, device: DeviceInfo) -> AuthResponse:
        user = self.users.by_identifier(identifier)
        if user is None or not security.verify_password(password, user.password_hash):
            raise UnauthorizedError("Incorrect email, username, or password.", code="bad_credentials", retryable=True)
        if user.status == UserStatus.SUSPENDED:
            raise ForbiddenSignIn()
        token_pair, device_id = await self._create_device(user.id, device)
        user.last_seen_at = datetime.now(timezone.utc)
        self.commit()
        return AuthResponse(tokens=token_pair, user=_user_to_me(user), registered=False)

    async def refresh(self, *, refresh_token: str, device_info: Optional[DeviceInfo] = None) -> TokenPair:
        digest = hash_refresh_token(refresh_token)
        device = self.devices.by_refresh_hash(digest)
        if device is None or device.revoked_at is not None:
            raise UnauthorizedError("This session is no longer valid. Please sign in again.", code="invalid_refresh")
        user = self.users.get(device.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise UnauthorizedError("This account is no longer active.", code="account_inactive")

        new_device_pair, _ = await self._create_device(
            user.id, device_info or _default_device(), current_of=device.id
        )
        device.revoked_at = datetime.now(timezone.utc)  # rotate old device entry
        self.commit()
        return new_device_pair

    async def logout(self, user_id: str, device_id: Optional[str]) -> None:
        if device_id:
            device = self.devices.get(device_id)
            if device and device.user_id == user_id:
                device.revoked_at = datetime.now(timezone.utc)
            self.commit()
            return
        now = datetime.now(timezone.utc)
        for d in self.devices.by_user(user_id):
            d.revoked_at = now
        self.commit()

    async def revoke_device(self, user_id: str, target_device_id: str) -> None:
        device = self.devices.get(target_device_id)
        if device is None or device.user_id != user_id:
            raise NotFoundError("Device not found.")
        device.revoked_at = datetime.now(timezone.utc)
        device.is_current = False
        self.commit()

    def list_devices(self, user_id: str, current_device_id: Optional[str] = None) -> list[DevicePublic]:
        return [
            DevicePublic.model_validate(d)
            for d in self.devices.by_user(user_id)
        ]

    # ------------------------------------------------------------------ #
    # Password management
    # ------------------------------------------------------------------ #

    def change_password(self, user_id: str, *, current_password: str, new_password: str) -> None:
        user = self.users.get(user_id)
        if user is None or not security.verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Your current password is incorrect.", code="wrong_password")
        user.password_hash = security.hash_password(new_password)
        now = datetime.now(timezone.utc)
        for d in self.devices.by_user(user_id):
            d.revoked_at = now  # revoke all sessions on password change
        self.commit()

    def request_password_reset(self, email: str) -> str:
        """Issues an expiring reset token. Returns it for dev; production emails it."""
        user = self.users.by_email(email)
        if user is None:
            # Do not reveal whether an account exists.
            return "sent"
        token = security.generate_opaque_token(32)
        user.reset_token_hash = hash_refresh_token(token)
        user.reset_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        self.commit()
        return token

    def reset_password(self, *, reset_token: str, new_password: str) -> bool:
        from sqlalchemy import select

        digest = hash_refresh_token(reset_token)
        user = self.db.scalar(
            select(User).where(User.reset_token_hash == digest)
        )
        if user is None:
            raise UnauthorizedError(
                "This reset link is invalid or has expired.", code="invalid_reset_token"
            )
        from app.core.timeutil import ensure_utc

        expires = ensure_utc(user.reset_token_expires_at)
        if expires is None or expires < datetime.now(timezone.utc):
            raise UnauthorizedError(
                "This reset link has expired. Please request a new one.", code="reset_token_expired"
            )
        user.password_hash = security.hash_password(new_password)
        user.reset_token_hash = None
        user.reset_token_expires_at = None
        now = datetime.now(timezone.utc)
        for d in self.devices.by_user(user.id):
            d.revoked_at = now
        self.commit()
        return True

    def verify_email(self, user_id: str, code: str) -> bool:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if user.email_verified:
            return True
        digest = hash_verification(code)
        if user.verification_code_hash != digest:
            raise UnauthorizedError("That verification code is incorrect.", code="bad_verification")
        from app.core.timeutil import ensure_utc

        expires = ensure_utc(user.verification_code_expires_at)
        if expires is None or expires < datetime.now(timezone.utc):
            raise UnauthorizedError("That verification code has expired.", code="verification_expired")
        user.email_verified = True
        user.verification_code_hash = None
        user.verification_code_expires_at = None
        self.commit()
        return True

    def issue_email_verification(self, user_id: str) -> str:
        """Creates a verification code (dev returns it; production emails it)."""
        user = self.users.get(user_id)
        if user is None or user.email_verified:
            return "verified"
        code = f"{secrets.randbelow(1_000_000):06d}"
        user.verification_code_hash = hash_verification(code)
        user.verification_code_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        self.commit()
        return code

    # ------------------------------------------------------------------ #
    # Account deletion
    # ------------------------------------------------------------------ #

    async def delete_account(self, user_id: str, *, password: str, confirmation: str) -> None:
        if confirmation != "DELETE":
            raise ValidationAppError("Type DELETE to confirm account deletion.", code="bad_confirmation")
        user = self.users.get(user_id)
        if user is None or not security.verify_password(password, user.password_hash):
            raise UnauthorizedError("Your password is incorrect.", code="wrong_password")
        user.status = UserStatus.DELETED
        user.deleted_at = datetime.now(timezone.utc)
        user.email = f"deleted-{user_id}@envychat.invalid"
        user.username = f"deleted_{user_id}"[:20]
        for d in self.devices.by_user(user_id, include_revoked=True):
            d.revoked_at = datetime.now(timezone.utc)
        self.commit()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    async def _create_device(
        self,
        user_id: str,
        info: DeviceInfo,
        *,
        current_of: Optional[str] = None,
    ) -> tuple[TokenPair, str]:
        refresh_token = security.generate_opaque_token(48)
        device = Device(
            user_id=user_id,
            platform=DevicePlatform(info.platform or "ios"),
            device_name=info.device_name or "iPhone",
            os_version=info.os_version,
            app_version=info.app_version,
            push_token=info.push_token,
            refresh_token_hash=hash_refresh_token(refresh_token),
            last_used_at=datetime.now(timezone.utc),
        )
        self.devices.add(device)
        self.flush()
        if current_of is None:
            self.devices.revoke_others(user_id, device.id)
        access = security.issue_access_token(
            user_id, claims={"dev": device.id, "platform": info.platform or "ios"}
        )
        pair = TokenPair(
            access_token=access,
            refresh_token=refresh_token,
            expires_in=settings.access_token_ttl_minutes * 60,
            device_id=device.id,
        )
        return pair, device.id


def _default_device() -> DeviceInfo:
    return DeviceInfo(platform="ios", device_name="iPhone")


class ForbiddenSignIn(UnauthorizedError):
    status_code = 403
    code = "account_suspended"
    message = "This account is suspended. Please contact support."