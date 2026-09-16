"""Notification service: inbox rows + APNs dispatch seam."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.core.constants import NotificationKind
from app.core.events import Envelope, EventType
from app.models.notification import Notification, NotificationPreference
from app.repositories.notification_repo import (
    NotificationPrefRepository,
    NotificationRepository,
)
from app.schemas.notification import NotificationOut
from app.services.base import Service


class NotificationService(Service):
    def __init__(self, db: Session, **kwargs):
        super().__init__(db, **kwargs)
        self.notifications = NotificationRepository(db)
        self.prefs = NotificationPrefRepository(db)

    def create(self, *, user_id: str, kind: NotificationKind, title: str, body: Optional[str] = None,
               data: Optional[dict] = None, push: bool = True) -> Notification:
        row = Notification(user_id=user_id, kind=kind, title=title, body=body, data=data)
        self.notifications.add(row)
        self.db.flush()
        return row

    async def notify(self, *, user_id: str, kind: NotificationKind, title: str, body: Optional[str] = None,
                     data: Optional[dict] = None, push: bool = True) -> None:
        row = self.create(user_id=user_id, kind=kind, title=title, body=body, data=data)
        self.db.commit()
        await self.ws.send_to_user(
            user_id,
            Envelope(type=EventType.NOTIFICATION_CREATED, data={"notification": self._to_out(row).model_dump()}),
        )
        if push and push_enabled_for(self.prefs, user_id, kind):
            # APNs dispatch is a seam: production injects the provider.
            pass  # self._dispatch_apns(...)

    def list_for_user(self, user_id: str, limit: int, before_id: Optional[int] = None):
        rows = self.notifications.list_for_user(user_id, limit, before_id)
        return [self._to_out(r) for r in rows]

    def mark_all_read(self, user_id: str) -> None:
        self.notifications.mark_all_read(user_id)
        self.db.commit()

    async def mark_read(self, user_id: str, notification_id: int) -> None:
        row = self.notifications.get(notification_id)
        if row is None or row.user_id != user_id:
            return
        from datetime import datetime, timezone

        row.read_at = datetime.now(timezone.utc)
        self.db.commit()

    def unread_count(self, user_id: str) -> int:
        from sqlalchemy import func, select

        from app.models.notification import Notification

        return int(self.db.scalar(select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id, Notification.read_at.is_(None)
        )) or 0)

    # ------------------------------------------------------------------ #
    # Preferences
    # ------------------------------------------------------------------ #

    def get_prefs(self, user_id: str) -> NotificationPreference:
        prefs = self.prefs.by_user(user_id)
        if prefs is None:
            prefs = NotificationPreference(user_id=user_id)
            self.prefs.add(prefs)
            self.db.commit()
        return prefs

    def update_prefs(self, user_id: str, payload) -> NotificationPreference:
        prefs = self.get_prefs(user_id)
        for field in (
            "messages_enabled",
            "groups_enabled",
            "calls_enabled",
            "streak_notifications",
            "streak_reminders",
            "friend_requests",
            "security_alerts",
            "show_preview",
            "quiet_hours_enabled",
            "quiet_hours_start",
            "quiet_hours_end",
        ):
            value = getattr(payload, field, None)
            if value is not None:
                setattr(prefs, field, value)
        self.db.commit()
        return prefs

    @staticmethod
    def _to_out(row: Notification) -> NotificationOut:
        return NotificationOut(
            id=row.id,
            kind=row.kind,
            title=row.title,
            body=row.body,
            data=row.data,
            read_at=row.read_at,
            created_at=row.created_at,
        )


def push_enabled_for(prefs_repo, user_id: str, kind: NotificationKind) -> bool:
    prefs = prefs_repo.by_user(user_id)
    if prefs is None:
        return True
    switch = {
        NotificationKind.MESSAGE: "messages_enabled",
        NotificationKind.GROUP_MESSAGE: "groups_enabled",
        NotificationKind.FRIEND_REQUEST: "friend_requests",
        NotificationKind.CALL: "calls_enabled",
        NotificationKind.STREAK: "streak_notifications",
        NotificationKind.STREAK_MILESTONE: "streak_notifications",
        NotificationKind.STREAK_REMINDER: "streak_reminders",
        NotificationKind.SECURITY: "security_alerts",
    }.get(kind)
    return getattr(prefs, switch, True) if switch else True