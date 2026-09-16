"""Notification routes."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, get_ws_manager
from app.schemas.notification import (
    NotificationPreferencesOut,
    PushTokenPayload,
    UpdateNotificationPreferencesPayload,
)
from app.services.notification_service import NotificationService
from app.services.auth_service import AuthService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def svc(db: Session) -> NotificationService:
    return NotificationService(db, redis=get_ws_manager()._redis, ws=get_ws_manager())


@router.get("")
async def list_notifications(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    before_id: Annotated[Optional[int], Query()] = None,
    db: SessionDep = None,
    user: CurrentUser = None,
):
    return {"items": svc(db).list_for_user(user.id, limit, before_id)}


@router.post("/read-all", status_code=204)
async def read_all(db: SessionDep, user: CurrentUser):
    svc(db).mark_all_read(user.id)


@router.post("/{notification_id}/read", status_code=204)
async def read_one(notification_id: int, db: SessionDep, user: CurrentUser):
    await svc(db).mark_read(user.id, notification_id)


@router.get("/unread-count")
async def unread_count(db: SessionDep, user: CurrentUser):
    return {"count": svc(db).unread_count(user.id)}


@router.get("/preferences")
async def get_prefs(db: SessionDep, user: CurrentUser) -> NotificationPreferencesOut:
    return NotificationPreferencesOut.model_validate(svc(db).get_prefs(user.id))


@router.patch("/preferences")
async def update_prefs(payload: UpdateNotificationPreferencesPayload, db: SessionDep, user: CurrentUser) -> NotificationPreferencesOut:
    updated = svc(db).update_prefs(user.id, payload)
    return NotificationPreferencesOut.model_validate(updated)


@router.post("/push-token", status_code=204)
async def register_push_token(payload: PushTokenPayload, db: SessionDep, user: CurrentUser):
    auth = AuthService(db)
    device = auth.devices.get(payload.device_id)
    if device and device.user_id == user.id:
        device.push_token = payload.push_token
        db.commit()
    return None