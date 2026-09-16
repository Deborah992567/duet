"""Call routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, get_ws_manager
from app.core.constants import CallKind
from app.schemas.call import AnswerCallPayload, CallList, CallOut, EndCallPayload, StartCallPayload
from app.services.call_service import CallService

router = APIRouter(prefix="/calls", tags=["calls"])


def svc(db: Session) -> CallService:
    return CallService(db, redis=get_ws_manager()._redis, ws=get_ws_manager())


@router.post("", status_code=201)
async def start_call(payload: StartCallPayload, db: SessionDep, user: CurrentUser) -> CallOut:
    return await svc(db).start(user.id, payload.conversation_id, payload.kind)


@router.post("/{call_id}/answer")
async def answer_call(call_id: str, payload: AnswerCallPayload, db: SessionDep, user: CurrentUser):
    state = await svc(db).answer(user.id, call_id, payload.accept)
    return {"state": state}


@router.post("/{call_id}/end")
async def end_call(call_id: str, payload: EndCallPayload, db: SessionDep, user: CurrentUser) -> CallOut:
    return await svc(db).end(user.id, call_id)


@router.get("/history")
async def history(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: SessionDep = None,
    user: CurrentUser = None,
) -> CallList:
    return svc(db).history(user.id, limit, offset)