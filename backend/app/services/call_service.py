"""Call service: call lifecycle and history.

Real-time media transport (WebRTC/SFU) is out of scope for the initial
release; this service owns call *state* (kind, direction, state machine,
history) and emits signaling-agnostic events so a transport can be attached
without restructuring the messaging system.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.constants import CallDirection, CallKind, CallState
from app.core.errors import ForbiddenError, NotFoundError
from app.models.call import Call, CallParticipant
from app.repositories.call_repo import CallParticipantRepository, CallRepository
from app.repositories.conversation_repo import ConversationMemberRepository, ConversationRepository
from app.repositories.user_repo import UserRepository
from app.schemas.call import CallList, CallOut
from app.services.base import Service


class CallService(Service):
    def __init__(self, db: Session, **kwargs):
        super().__init__(db, **kwargs)
        self.calls = CallRepository(db)
        self.participants = CallParticipantRepository(db)
        self.members = ConversationMemberRepository(db)
        self.conversations = ConversationRepository(db)
        self.users = UserRepository(db)

    async def start(self, actor_id: str, conversation_id: str, kind: CallKind) -> CallOut:
        member = self.members.member(conversation_id, actor_id)
        if member is None or member.left_at is not None:
            raise ForbiddenError("You are not part of this conversation.")
        members = self.members.member_ids(conversation_id)
        peer = next((m for m in members if m != actor_id), None)
        if peer is None:
            raise ForbiddenError("A call requires at least one other participant.")

        call = Call(
            conversation_id=conversation_id,
            initiator_id=actor_id,
            kind=kind,
            direction=CallDirection.OUTGOING,
            state=CallState.RINGING,
            peer_user_id=peer,
        )
        self.calls.add(call)
        self.db.flush()
        self.participants.add(
            CallParticipant(call_id=call.id, user_id=actor_id, role="initiator")
        )
        self.db.commit()
        out = self._to_out(call)
        from app.core.events import Envelope, EventType

        await self.ws.send_to_user(
            peer,
            Envelope(
                type=EventType.CALL_RECEIVED,
                conversation_id=conversation_id,
                data={"call": out.model_dump()},
            ),
        )
        return out

    async def answer(self, actor_id: str, call_id: str, accept: bool) -> CallState:
        call = self.calls.get(call_id)
        if call is None:
            raise NotFoundError("Call not found.")
        if call.peer_user_id != actor_id and call.initiator_id != actor_id:
            raise ForbiddenError("You are not part of this call.")
        from app.core.events import Envelope, EventType

        if not accept:
            call.state = CallState.REJECTED
            call.ended_at = datetime.now(timezone.utc)
            self.db.commit()
            await self.ws.send_to_user(
                call.initiator_id,
                Envelope(type=EventType.CALL_UPDATED, conversation_id=call.conversation_id,
                         data={"call": self._to_out(call).model_dump()}),
            )
            return call.state

        call.state = CallState.ACTIVE
        call.started_at = call.started_at or datetime.now(timezone.utc)
        participant = self.participants.add(
            CallParticipant(call_id=call.id, user_id=actor_id, role="callee", answered_at=datetime.now(timezone.utc))
        )
        self.db.commit()
        await self.ws.send_to_users(
            [call.initiator_id, actor_id],
            Envelope(type=EventType.CALL_UPDATED, conversation_id=call.conversation_id,
                     data={"call": self._to_out(call).model_dump()}),
        )
        return call.state

    async def end(self, actor_id: str, call_id: str) -> CallOut:
        call = self.calls.get(call_id)
        if call is None:
            raise NotFoundError("Call not found.")
        now = datetime.now(timezone.utc)
        if call.state in (CallState.ACTIVE, CallState.CONNECTING, CallState.RINGING):
            if call.ended_at is None:
                call.ended_at = now
            call.state = CallState.ENDED
            if call.started_at:
                call.duration_seconds = max(0, int((now - call.started_at).total_seconds()))
            else:
                call.duration_seconds = 0
        self.db.commit()
        out = self._to_out(call)
        from app.core.events import Envelope, EventType

        await self.ws.send_to_users(
            [call.initiator_id, call.peer_user_id],
            Envelope(type=EventType.CALL_UPDATED, conversation_id=call.conversation_id,
                     data={"call": out.model_dump()}),
        )
        return out

    def history(self, user_id: str, limit: int, offset: int = 0) -> CallList:
        rows = self.calls.history_for(user_id, limit, offset)
        return CallList(items=[self._to_out(c) for c in rows], has_more=len(rows) == limit)

    def record_missed(self, call_id: str) -> CallOut:
        call = self.calls.get(call_id)
        if call and call.state == CallState.RINGING:
            call.state = CallState.MISSED
            call.ended_at = call.ended_at or datetime.now(timezone.utc)
            self.db.commit()
        return self._to_out(call)

    @staticmethod
    def _to_out(call: Call) -> CallOut:
        return CallOut(
            id=call.id,
            conversation_id=call.conversation_id,
            initiator_id=call.initiator_id,
            kind=call.kind,
            direction=call.direction,
            state=call.state,
            started_at=call.started_at,
            ended_at=call.ended_at,
            duration_seconds=call.duration_seconds,
            peer_user_id=call.peer_user_id,
            created_at=call.created_at,
        )