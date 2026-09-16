"""Friendship routes: requests, accept/decline, friends list, mutuals."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, get_ws_manager
from app.schemas.friend import (
    RemoveFriendPayload,
    RespondFriendRequestPayload,
    SendFriendRequestPayload,
)
from app.services.friendship_service import FriendshipService

router = APIRouter(prefix="/friends", tags=["friends"])


def svc(db: Session) -> FriendshipService:
    return FriendshipService(db, redis=get_ws_manager()._redis, ws=get_ws_manager())


@router.post("/requests")
async def send_request(payload: SendFriendRequestPayload, db: SessionDep, user: CurrentUser):
    request = await svc(db).send_request(user.id, payload.user_id, payload.message)
    return {"request_id": request.id, "status": "pending"}


@router.get("/requests/incoming")
async def incoming(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: SessionDep = None,
    user: CurrentUser = None,
):
    return await svc(db).list_incoming(user.id, limit)


@router.get("/requests/outgoing")
async def outgoing(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    db: SessionDep = None,
    user: CurrentUser = None,
):
    return await svc(db).list_outgoing(user.id, limit)


@router.post("/requests/{request_id}/respond", status_code=204)
async def respond(request_id: str, payload: RespondFriendRequestPayload, db: SessionDep, user: CurrentUser):
    if payload.accept:
        await svc(db).accept_request(user.id, request_id)
    else:
        await svc(db).decline_request(user.id, request_id)


@router.post("/requests/{request_id}/cancel", status_code=204)
async def cancel(request_id: str, db: SessionDep, user: CurrentUser):
    await svc(db).cancel_request(user.id, request_id)


@router.get("")
async def list_friends(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: SessionDep = None,
    user: CurrentUser = None,
):
    return svc(db).list_friends(user.id, limit, offset)


@router.delete("")
async def remove_friend(payload: RemoveFriendPayload, db: SessionDep, user: CurrentUser):
    await svc(db).remove_friend(user.id, payload.user_id)
    return {"status": "removed"}


@router.get("/mutual/{peer_id}")
async def mutual(peer_id: str, db: SessionDep, user: CurrentUser):
    return svc(db).list_mutual(user.id, peer_id)