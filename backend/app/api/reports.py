"""Report and app-settings routes."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, get_ws_manager
from app.schemas.friend import ReportUserPayload
from app.schemas.report import CreateReportPayload
from app.services.report_service import ReportService, SettingsService

router = APIRouter(prefix="/reports", tags=["reports"])


def svc(db: Session) -> ReportService:
    return ReportService(db, redis=get_ws_manager()._redis, ws=get_ws_manager())


@router.post("", status_code=201)
async def create_report(payload: CreateReportPayload, db: SessionDep, user: CurrentUser):
    row = await svc(db).create(user.id, payload)
    return {"report_id": row.id, "status": "received"}


@router.post("/legacy-user")
async def legacy_report(payload: ReportUserPayload, db: SessionDep, user: CurrentUser):
    converted = CreateReportPayload(
        kind="user",
        target_user_id=payload.user_id,
        message_id=payload.message_id,
        reason=payload.reason,
        description=payload.description,
    )
    row = await svc(db).create(user.id, converted)
    return {"report_id": row.id, "status": "received"}


settings_router = APIRouter(prefix="/app", tags=["app"])


@settings_router.get("/version")
async def app_version(db: SessionDep = None):
    return SettingsService(db).app_version()