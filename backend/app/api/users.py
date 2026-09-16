"""User, profile, search, block, and privacy routes."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, get_ws_manager
from app.schemas.user import (
    BlockedUserPublic,
    PrivacySettingsPayload,
    UpdateProfileRequest,
    UserPublic,
    UserSearchResult,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


def svc(db: Session) -> UserService:
    return UserService(db, redis=get_ws_manager()._redis, ws=get_ws_manager())


@router.get("/me")
async def me(db: SessionDep, user: CurrentUser):
    return UserService(db).get_me(user.id)


@router.patch("/me")
async def update_me(payload: UpdateProfileRequest, db: SessionDep, user: CurrentUser) -> UserPublic:
    return UserService(db).update_profile(user.id, payload)


@router.patch("/me/privacy")
async def update_privacy(payload: PrivacySettingsPayload, db: SessionDep, user: CurrentUser):
    from app.services.user_service import to_public

    updated = svc(db).update_privacy(
        user.id,
        read_receipts=payload.read_receipts_enabled,
        show_online=payload.show_online_status,
        visibility=payload.profile_visibility,
        allow_preview=payload.notification_preview_allowed,
    )
    return to_public(updated)


@router.get("/search")
async def search_users(
    q: str = Query(min_length=2, max_length=80),
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    db: SessionDep = None,
    user: CurrentUser = None,
) -> UserSearchResult:
    return svc(db).search_users(user.id, q, limit)


@router.get("/{user_id}")
async def get_user(user_id: str, db: SessionDep, user: CurrentUser) -> UserPublic:
    return svc(db).get_user_public(user.id, user_id)


@router.post("/{user_id}/block", status_code=204)
async def block_user(user_id: str, db: SessionDep, user: CurrentUser):
    await svc(db).block_user(user.id, user_id)


@router.delete("/{user_id}/block", status_code=204)
async def unblock_user(user_id: str, db: SessionDep, user: CurrentUser):
    await svc(db).unblock_user(user.id, user_id)


@router.get("/blocked/list")
async def list_blocked(db: SessionDep, user: CurrentUser) -> list[BlockedUserPublic]:
    return svc(db).list_blocked(user.id)