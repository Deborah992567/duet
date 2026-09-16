"""Conversation routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, get_ws_manager
from app.schemas.conversation import (
    AddMembersPayload,
    ConversationDetail,
    ConversationList,
    CreateDirectConversationPayload,
    CreateGroupPayload,
    DemoteMemberPayload,
    MarkReadPayload,
    MutePayload,
    PinPayload,
    PromoteMemberPayload,
    RemoveMemberPayload,
    UpdateGroupPayload,
)
from app.services.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["conversations"])


def svc(db: Session) -> ConversationService:
    return ConversationService(db, redis=get_ws_manager()._redis, ws=get_ws_manager())


@router.get("")
async def list_conversations(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    db: SessionDep = None,
    user: CurrentUser = None,
) -> ConversationList:
    return svc(db).list_for_user(user.id, limit)


@router.post("", status_code=201)
async def create(payload: CreateDirectConversationPayload, db: SessionDep, user: CurrentUser) -> ConversationDetail:
    return await svc(db).create_direct(user.id, payload.user_id)


@router.get("/{conversation_id}")
async def detail(conversation_id: str, db: SessionDep, user: CurrentUser) -> ConversationDetail:
    return svc(db).get_detail(user.id, conversation_id)


@router.post("/groups", status_code=201)
async def create_group(payload: CreateGroupPayload, db: SessionDep, user: CurrentUser) -> ConversationDetail:
    return await svc(db).create_group(user.id, payload)


@router.patch("/{conversation_id}/group")
async def update_group(conversation_id: str, payload: UpdateGroupPayload, db: SessionDep, user: CurrentUser) -> ConversationDetail:
    return await svc(db).update_group(user.id, conversation_id, payload)


@router.post("/{conversation_id}/members", status_code=204)
async def add_members(conversation_id: str, payload: AddMembersPayload, db: SessionDep, user: CurrentUser):
    await svc(db).add_members(user.id, conversation_id, payload)


@router.delete("/{conversation_id}/members/{user_id}", status_code=204)
async def remove_member(conversation_id: str, user_id: str, db: SessionDep, user: CurrentUser):
    await svc(db).remove_member(user.id, conversation_id, user_id)


@router.post("/{conversation_id}/members/{user_id}/promote", status_code=204)
async def promote(conversation_id: str, user_id: str, db: SessionDep, user: CurrentUser):
    await svc(db).promote(user.id, conversation_id, user_id)


@router.post("/{conversation_id}/members/{user_id}/demote", status_code=204)
async def demote(conversation_id: str, user_id: str, db: SessionDep, user: CurrentUser):
    await svc(db).demote(user.id, conversation_id, user_id)


@router.post("/{conversation_id}/leave", status_code=204)
async def leave(conversation_id: str, db: SessionDep, user: CurrentUser):
    await svc(db).leave_group(user.id, conversation_id)


@router.post("/{conversation_id}/read", status_code=204)
async def mark_read(conversation_id: str, payload: MarkReadPayload, db: SessionDep, user: CurrentUser):
    await svc(db).mark_read(user.id, conversation_id, payload.up_to_message_id)


@router.post("/{conversation_id}/mute", status_code=204)
async def mute(conversation_id: str, payload: MutePayload, db: SessionDep, user: CurrentUser):
    await svc(db).set_muted(user.id, conversation_id, payload.muted)


@router.post("/{conversation_id}/pin", status_code=204)
async def pin(conversation_id: str, payload: PinPayload, db: SessionDep, user: CurrentUser):
    await svc(db).set_pinned(user.id, conversation_id, payload.pinned)


@router.delete("/{conversation_id}", status_code=204)
async def hide(conversation_id: str, db: SessionDep, user: CurrentUser):
    await svc(db).hide_conversation(user.id, conversation_id)