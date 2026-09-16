"""Streak routes (read + user settings; engine is write-path)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, get_ws_manager
from app.schemas.streak import StreakSettingsPayload
from app.services.report_service import StreakQueryService

router = APIRouter(prefix="/streaks", tags=["streaks"])


def svc(db: Session) -> StreakQueryService:
    return StreakQueryService(db, redis=get_ws_manager()._redis, ws=get_ws_manager())


@router.get("/{conversation_id}/with/{peer_id}")
async def between(conversation_id: str, peer_id: str, db: SessionDep, user: CurrentUser):
    return svc(db).between(user.id, peer_id, conversation_id)


@router.get("/history/{conversation_id}/with/{peer_id}")
async def history(conversation_id: str, peer_id: str, db: SessionDep, user: CurrentUser):
    return {"items": svc(db).history(user.id, peer_id, conversation_id)}


@router.get("/me")
async def my_streaks(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: SessionDep = None,
    user: CurrentUser = None,
):
    from app.schemas.streak import StreakSummary
    from app.services.user_service import to_public

    rows = svc(db).list_for_user(user.id, limit, offset)
    return [
        StreakSummary(
            user_id=r["user_id"],
            peer_user_id=r["peer_user_id"],
            conversation_id=r["conversation_id"],
            current_streak=r["current_streak"],
            longest_streak=r["longest_streak"],
            alive=r["alive"],
            last_activity_day=r["prepared_at"],
            peer=to_public(r["peer"]) if r.get("peer") else None,
        )
        for r in rows
    ]


@router.patch("/me/settings")
async def update_settings(payload: StreakSettingsPayload, db: SessionDep, user: CurrentUser):
    return svc(db).update_user_settings(user.id, payload)