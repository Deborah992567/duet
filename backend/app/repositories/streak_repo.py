"""Streak repository."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.models.streak import Streak, StreakDayQualification, StreakEvent
from app.repositories.base import BaseRepository


class StreakRepository(BaseRepository[Streak]):
    model = Streak

    def by_triple(self, user_id: str, peer_user_id: str, conversation_id: str) -> Streak | None:
        return self.db.scalar(
            select(Streak).where(
                Streak.user_id == user_id,
                Streak.peer_user_id == peer_user_id,
                Streak.conversation_id == conversation_id,
            )
        )

    def list_for_user(self, user_id: str, limit: int = 50, offset: int = 0) -> list[Streak]:
        return list(
            self.db.scalars(
                select(Streak)
                .where(Streak.user_id == user_id)
                .order_by(Streak.prepared_at.desc().nullslast())
                .limit(limit)
                .offset(offset)
            ).all()
        )


class StreakDayRepository(BaseRepository[StreakDayQualification]):
    model = StreakDayQualification

    def by_day(self, user_id: str, conversation_id: str, day: date) -> StreakDayQualification | None:
        return self.db.scalar(
            select(StreakDayQualification).where(
                StreakDayQualification.user_id == user_id,
                StreakDayQualification.conversation_id == conversation_id,
                StreakDayQualification.day == day,
            )
        )


class StreakEventRepository(BaseRepository[StreakEvent]):
    model = StreakEvent

    def history(
        self, user_id: str, peer_user_id: str, conversation_id: str, limit: int = 100
    ) -> list[StreakEvent]:
        return list(
            self.db.scalars(
                select(StreakEvent)
                .where(
                    StreakEvent.user_id == user_id,
                    StreakEvent.peer_user_id == peer_user_id,
                    StreakEvent.conversation_id == conversation_id,
                )
                .order_by(StreakEvent.day.desc(), StreakEvent.id.desc())
                .limit(limit)
            ).all()
        )