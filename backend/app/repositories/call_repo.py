"""Call repository."""

from __future__ import annotations

from sqlalchemy import or_, select

from app.models.call import Call, CallParticipant
from app.repositories.base import BaseRepository


class CallRepository(BaseRepository[Call]):
    model = Call

    def history_for(self, user_id: str, limit: int, offset: int = 0) -> list[Call]:
        return list(
            self.db.scalars(
                select(Call)
                .where(or_(Call.initiator_id == user_id, Call.peer_user_id == user_id))
                .order_by(Call.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )


class CallParticipantRepository(BaseRepository[CallParticipant]):
    model = CallParticipant