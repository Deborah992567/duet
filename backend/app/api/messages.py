"""Message routes."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Query
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, SessionDep, get_ws_manager
from app.schemas.message import (
    DeleteMessagePayload,
    EditMessagePayload,
    ForwardMessagePayload,
    MessageList,
    ReactPayload,
    SearchMessagesPayload,
    SendMessagePayload,
    SendMessageResult,
)
from app.services.message_service import MessageService

router = APIRouter(prefix="/conversations", tags=["messages"])


def svc(db: Session) -> MessageService:
    return MessageService(db, redis=get_ws_manager()._redis, ws=get_ws_manager())


@router.post("/{conversation_id}/messages")
async def send(conversation_id: str, payload: SendMessagePayload, db: SessionDep, user: CurrentUser) -> SendMessageResult:
    payload.conversation_id = conversation_id
    return await svc(db).send(user.id, payload)


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: str,
    before: Annotated[Optional[int], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    db: SessionDep = None,
    user: CurrentUser = None,
) -> MessageList:
    return svc(db).list_before(user.id, conversation_id, before, limit)


@router.patch("/{conversation_id}/messages/{message_id}")
async def edit(
    conversation_id: str, message_id: str, payload: EditMessagePayload, db: SessionDep, user: CurrentUser
):
    from app.schemas.message import MessageOut

    return await svc(db).edit(user.id, message_id, payload)


@router.delete("/{conversation_id}/messages/{message_id}", status_code=204)
async def delete(
    conversation_id: str, message_id: str, payload: DeleteMessagePayload, db: SessionDep, user: CurrentUser
):
    await svc(db).delete(user.id, message_id, payload.delete_for)


@router.post("/{conversation_id}/messages/{message_id}/react", status_code=204)
async def react(conversation_id: str, message_id: str, payload: ReactPayload, db: SessionDep, user: CurrentUser):
    await svc(db).react(user.id, message_id, payload.emoji, payload.reaction_type.value)


@router.delete("/{conversation_id}/messages/{message_id}/react/{emoji}", status_code=204)
async def unreact(conversation_id: str, message_id: str, emoji: str, db: SessionDep, user: CurrentUser):
    await svc(db).unreact(user.id, message_id, emoji)


@router.post("/messages/forward")
async def forward(payload: ForwardMessagePayload, db: SessionDep, user: CurrentUser):
    return await svc(db).forward(user.id, payload.message_id, payload.to_conversation_ids)


@router.post("/messages/search")
async def search(payload: SearchMessagesPayload, db: SessionDep, user: CurrentUser) -> MessageList:
    return svc(db).search(user.id, payload.query, payload.conversation_id, payload.limit)


@router.post("/{conversation_id}/typing", status_code=204)
async def typing_started(conversation_id: str, db: SessionDep, user: CurrentUser):
    await svc(db).typing_started(user.id, conversation_id)


@router.delete("/{conversation_id}/typing", status_code=204)
async def typing_stopped(conversation_id: str, db: SessionDep, user: CurrentUser):
    await svc(db).typing_stopped(user.id, conversation_id)


@router.post("/{conversation_id}/receipts/delivered", status_code=204)
async def confirm_delivery(conversation_id: str, payload: dict, db: SessionDep, user: CurrentUser):
    message_ids = payload.get("message_ids", [])
    await svc(db).confirm_delivery(user.id, conversation_id, message_ids)


@router.post("/{conversation_id}/receipts/read", status_code=204)
async def mark_read(conversation_id: str, payload: dict, db: SessionDep, user: CurrentUser):
    await svc(db).mark_read(user.id, conversation_id, payload.get("up_to_message_id"))