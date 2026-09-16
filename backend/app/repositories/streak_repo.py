"""Streak, notification, call, and report repositories."""

from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select

from app.models.call import Call, CallParticipant
from app.models.notification import Notification, NotificationPreference
from app.models.report import Report
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

    def all_with_peer_for_user(self, user_id: str) -> list[Streak]:
        return list(
            self.db.scalars(select(Streak).where(Streak.user_id == user_id)).all()
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

    def notification_active(self, user_id: str, peer_user_id: str, avg_day=0) -> None:
        """No-op placeholder to keep interface stable for future thinning."""
        return None


class StreakEventRepository(BaseRepository[StreakEvent]):
    model = StreakEvent

    def history(self, user_id: str, peer_user_id: str, conversation_id: str, limit: int = 100) -> list[StreakEvent]:
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


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    def list_for_user(self, user_id: str, limit: int, before_id: int | None = None) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if before_id is not None:
            stmt = stmt.where(Notification.id < before_id)
        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def mark_all_read(self, user_id: str) -> int:
        from datetime import datetime, timezone

        from sqlalchemy import update

        now = datetime.now(timezone.utc)
        result = self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=now)
        )
        return result.rowcount or 0


class NotificationPrefRepository(BaseRepository[NotificationPreference]):
    model = NotificationPreference

    def by_user(self, user_id: str) -> NotificationPreference | None:
        return self.db.scalar(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )


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


class ReportRepository(BaseRepository[Report]):
    model = Report

    def recent_open_by(self, reporter_id: str) -> bool:
        return self.exists(Report.reporter_id == reporter_id)