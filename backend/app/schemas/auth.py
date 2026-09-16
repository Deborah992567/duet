"""Authentication request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.constants import MAX_DISPLAY_NAME_LENGTH, MAX_USERNAME_LENGTH
from app.core.config import settings

USERNAME_RE = r"^[a-z0-9_]{3," + str(MAX_USERNAME_LENGTH) + r"}$"


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=MAX_USERNAME_LENGTH)
    password: str = Field(min_length=settings.password_min_length, max_length=128)
    display_name: str = Field(min_length=1, max_length=MAX_DISPLAY_NAME_LENGTH)

    @field_validator("username")
    @classmethod
    def _validate_username(cls, v: str) -> str:
        import re

        if not re.match(USERNAME_RE, v):
            raise ValueError(
                "Username must be 3-20 characters using lowercase letters, digits, or underscores."
            )
        return v


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=191)  # email or @username
    password: str = Field(min_length=1, max_length=128)


class DeviceInfo(BaseModel):
    platform: str = "ios"
    device_name: str = "iPhone"
    os_version: str | None = None
    app_version: str | None = None
    push_token: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    device_id: str


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class LogoutRequest(BaseModel):
    device_id: str | None = None  # None => sign out everywhere


class VerifyEmailRequest(BaseModel):
    code: str = Field(min_length=4, max_length=12)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class RequestPasswordResetRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    reset_token: str
    password: str = Field(min_length=settings.password_min_length, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=settings.password_min_length, max_length=128)


class AuthResponse(BaseModel):
    tokens: TokenPair
    user: "UserPublic"
    registered: bool = False


from app.schemas.user import UserPublic  # noqa: E402

AuthResponse.model_rebuild()