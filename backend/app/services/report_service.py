"""Report/moderation, streak-query, presence, and app-settings services."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.constants import CallKind, ReportKind
from app.core.events import Envelope, EventType
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.report import Report
from app.repositories.report_repo import ReportRepository
from app.repositories.user_repo import UserRepository
from app.schemas.report import CreateReportPayload
from app.services.base import Service
from app.services.streak_engine import StreakEngine


class ReportService(Service):
    def __init__(self, db: Session, **kwargs):
        super().__init__(db, **kwargs)
        self.reports = ReportRepository(db)
        self.users = UserRepository(db)

    async def create(self, reporter_id: str, payload: CreateReportPayload) -> Report:
        if self.reports.recent_open_by(reporter_id):
            raise ConflictError(
                "You already have an open report. We'll review it as soon as possible.",
                code="report_limit",
            )
        if payload.kind == ReportKind.USER:
            if not payload.target_user_id:
                raise ForbiddenError("A target user is required for user reports.")
            if payload.target_user_id == reporter_id:
                raise ForbiddenError("You cannot report yourself.")
        elif payload.kind == ReportKind.MESSAGE:
            if not payload.message_id:
                raise ForbiddenError("A message is required for message reports.")
        else:
            if not payload.conversation_id:
                raise ForbiddenError("A conversation is required for conversation reports.")
        row = Report(
            reporter_id=reporter_id,
            kind=payload.kind,
            target_user_id=payload.target_user_id,
            message_id=payload.message_id,
            conversation_id=payload.conversation_id,
            reason=payload.reason,
            description=payload.description,
        )
        self.reports.add(row)
        self.db.commit()
        return row


class StreakQueryService(Service):
    """Read-side aggregation over the streak engine (authoritative values)."""

    def __init__(self, db: Session, **kwargs):
        super().__init__(db, **kwargs)
        self.users = UserRepository(db)
        self._engine = StreakEngine(db=db, ws=self.ws)

    def between(self, user_id: str, peer_user_id: str, conversation_id: str) -> dict:
        return self._engine.live(user_id, peer_user_id, conversation_id)

    def list_for_user(self, user_id: str, limit: int = 50, offset: int = 0) -> list[dict]:
        from app.repositories.streak_repo import StreakRepository

        streaks = StreakRepository(self.db).list_for_user(user_id, limit, offset)
        peers = {u.id: u for u in self.users.by_ids([s.peer_user_id for s in streaks])}
        out = []
        for s in streaks:
            payload = self._engine.live(user_id, s.peer_user_id, s.conversation_id)
            payload["peer"] = peers.get(s.peer_user_id)
            out.append(payload)
        return out

    def history(self, user_id: str, peer_user_id: str, conversation_id: str, limit: int = 100) -> list[dict]:
        from app.repositories.streak_repo import StreakEventRepository

        rows = StreakEventRepository(self.db).history(user_id, peer_user_id, conversation_id, limit)
        return [
            {
                "event_type": r.event_type,
                "day": r.day,
                "streak_after": r.streak_after,
                "meta": r.meta,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    def update_user_settings(self, user_id: str, payload) -> dict:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if payload.notifications_enabled is not None:
            user.streak_notifications_enabled = payload.notifications_enabled
        if payload.reminders_enabled is not None:
            user.streak_reminders_enabled = payload.reminders_enabled
        if payload.freezes_enabled is not None:
            user.streak_freezes_enabled = payload.freezes_enabled
        if payload.visible is not None:
            user.streak_visible = payload.visible
        self.db.commit()
        return {
            "notifications_enabled": user.streak_notifications_enabled,
            "reminders_enabled": user.streak_reminders_enabled,
            "freezes_enabled": user.streak_freezes_enabled,
            "visible": user.streak_visible,
        }


class PresenceService(Service):
    def __init__(self, db: Session, **kwargs):
        super().__init__(db, **kwargs)
        self.users = UserRepository(db)

    async def heartbeat(self, user_id: str, status: str = "online") -> None:
        await self.ws.set_presence(user_id, status)
        user = self.users.get(user_id)
        if user:
            from datetime import datetime, timezone

            user.last_seen_at = datetime.now(timezone.utc)
        self.db.commit()

    async def notify_peers(self, user_id: str, status: str) -> None:
        envelope = Envelope(
            type=EventType.PRESENCE_CHANGED, data={"user_id": user_id, "status": status}
        )
        from app.repositories.friendship_repo import FriendshipRepository

        friend_ids = FriendshipRepository(self.db).friend_ids_of(user_id)
        if friend_ids:
            await self.ws.send_to_users(list(friend_ids), envelope)

    def status_of(self, user_id: str) -> str:
        return "online" if self.ws.is_online(user_id) else "offline"


class SettingsService(Service):
    def app_version(self) -> dict:
        return {
            "version": "1.0.0",
            "minimum_ios_version": "17.0",
            "force_update": False,
            "update_url": None,
        }