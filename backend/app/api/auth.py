"""Auth API routes."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, get_ws_manager
from app.core.config import settings
from app.core.errors import TooManyRequestsError
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RequestPasswordResetRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenPair,
    VerifyEmailRequest,
    DeviceInfo,
)
from app.schemas.user import DeleteAccountRequest, DevicePublic, UserMe
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _auth_service(db: Session):
    return AuthService(db, redis=get_ws_manager()._redis, ws=get_ws_manager())


@router.post("/register", status_code=201)
async def register(payload: RegisterRequest, db: SessionDep, request: Request):
    await _rate(request, "auth_register", key_from(payload.email), settings.rate_limit_auth_per_minute)
    result = await _auth_service(db).register(
        email=payload.email, username=payload.username, password=payload.password,
        display_name=payload.display_name, device=_device(request),
    )
    return result


@router.post("/login")
async def login(payload: LoginRequest, db: SessionDep, request: Request):
    await _rate(request, "auth_login", key_from(payload.identifier), settings.rate_limit_auth_per_minute)
    return await _auth_service(db).login(
        identifier=payload.identifier, password=payload.password, device=_device(request)
    )


@router.post("/refresh")
async def refresh(payload: RefreshRequest, db: SessionDep):
    return await _auth_service(db).refresh(refresh_token=payload.refresh_token)


@router.post("/logout", status_code=204)
async def logout(payload: LogoutRequest, db: SessionDep, user: CurrentUser):
    await _auth_service(db).logout(user.id, payload.device_id)


@router.post("/request-password-reset", status_code=202)
async def request_password_reset(payload: RequestPasswordResetRequest, db: SessionDep, request: Request):
    await _rate(request, "auth_reset", payload.email, settings.rate_limit_auth_per_minute)
    _auth_service(db).request_password_reset(payload.email)
    return {"status": "ok"}


@router.post("/reset-password", status_code=204)
async def reset_password(payload: ResetPasswordRequest, db: SessionDep):
    _auth_service(db).reset_password(reset_token=payload.reset_token, new_password=payload.password)


@router.post("/change-password", status_code=204)
async def change_password(payload: ChangePasswordRequest, db: SessionDep, user: CurrentUser):
    _auth_service(db).change_password(user.id, current_password=payload.current_password, new_password=payload.new_password)


@router.post("/verify-email", status_code=204)
async def verify_email(payload: VerifyEmailRequest, db: SessionDep, user: CurrentUser):
    _auth_service(db).verify_email(user.id, payload.code)


@router.post("/resend-verification", status_code=202)
async def resend_verification(payload: ResendVerificationRequest, db: SessionDep):
    from app.repositories.user_repo import UserRepository

    user = UserRepository(db).by_email(payload.email)
    _auth_service(db).issue_email_verification(user.id) if user else None
    return {"status": "ok"}


@router.get("/devices")
async def list_devices(db: SessionDep, user: CurrentUser) -> list[DevicePublic]:
    return _auth_service(db).list_devices(user.id)


@router.delete("/devices/{device_id}", status_code=204)
async def revoke_device(device_id: str, db: SessionDep, user: CurrentUser):
    await _auth_service(db).revoke_device(user.id, device_id)


@router.delete("/account", status_code=204)
async def delete_account(payload: DeleteAccountRequest, db: SessionDep, user: CurrentUser):
    await _auth_service(db).delete_account(user.id, password=payload.password, confirmation=payload.confirmation)


@router.get("/me")
async def me(db: SessionDep, user: CurrentUser) -> UserMe:
    from app.services.auth_service import _user_to_me

    return _user_to_me(user)


async def _rate(request: Request, bucket: str, key: str, limit: int) -> None:
    redis = get_ws_manager()._redis
    if redis is None:
        return
    from app.core.rate_limit import RateLimiter

    await RateLimiter(redis).hit(bucket, key, limit)


def key_from(value: str) -> str:
    return value.strip().lower()


def _device(request: Request) -> DeviceInfo:
    headers = request.headers
    return DeviceInfo(
        platform=headers.get("x-platform", "ios"),
        device_name=headers.get("x-device-name", "iPhone"),
        os_version=headers.get("x-os-version"),
        app_version=headers.get("x-app-version"),
        push_token=headers.get("x-push-token"),
    )