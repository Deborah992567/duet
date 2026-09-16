"""Notification repository."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update

from app.models.notification import Notification, NotificationPreference
from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    def list_for_user(self, user_id: str, limit: int, before_id: int | None = None) -> list[Notification]:
        stmt = select(Notification).where(Notification.user_id == user_id)
        if before_id is not None:
            stmt = stmt.where(Notification.id < before_id)
        stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def mark_all_read(self, user_id: str) -> int:
        result = self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
            .values(read_at=datetime.now(timezone.utc))
        )
        return result.rowcount or 0


class NotificationPrefRepository(BaseRepository[NotificationPreference]):
    model = NotificationPreference

    def by_user(self, user_id: str) -> NotificationPreference | None:
        return self.db.scalar(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )