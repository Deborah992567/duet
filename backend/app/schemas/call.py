"""Call schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.core.constants import CallDirection, CallKind, CallState


class StartCallPayload(BaseModel):
    conversation_id: str
    kind: CallKind = CallKind.VOICE


class CallOut(BaseModel):
    id: str
    conversation_id: str
    initiator_id: str
    kind: CallKind
    direction: CallDirection
    state: CallState
    started_at: datetime | None = None
    ended_at: datetime | None = None
    duration_seconds: int | None = None
    peer_user_id: str
    created_at: datetime
    model_config = {"from_attributes": True}


class AnswerCallPayload(BaseModel):
    call_id: str
    accept: bool


class EndCallPayload(BaseModel):
    call_id: str


class CallList(BaseModel):
    items: list[CallOut]
    has_more: bool = False
    next_cursor: str | None = None


class CallSignalPayload(BaseModel):
    """Interim signaling envelope until a dedicated WebRTC/SFU path lands."""

    call_id: str
    type: str  # offer | answer | ice-candidate | hangup
    payload: dict = {}