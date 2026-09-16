"""Deterministic streak engine (backend is the source of truth).

Definitions
-----------
A *streak round* between user A and user B in a direct conversation is a
calendar day (UTC) on which **both** participants sent at least one message.
`current_streak` = the number of consecutive completed rounds ending on the
most recent round day (`prepared_at`).

Rules
-----
- Rounds are ordered by day; the engine only ever moves `prepared_at` forward
  to the next consecutive day. Gaps and late arrivals are handled idempotently.
- A streak is *alive* if `prepared_at` is today or yesterday. Any other gap
  breaks it (a single missed day may be covered by a user-opt-in freeze).
- Milestones from settings are emitted once per crossing.
- All input is persisted state (message timestamps), never client claims, so
  recomputation is deterministic and auditable via `streak_events`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.events import Envelope, EventType
from app.core.logging import get_logger
from app.models.streak import Streak, StreakDayQualification, StreakEvent
from app.repositories.streak_repo import StreakDayRepository, StreakEventRepository, StreakRepository
from app.ws.manager import WSConnectionManager

logger = get_logger(__name__)

MILESTONES = sorted(settings.streak_milestones)


def utc_day(at: datetime | date) -> date:
    if isinstance(at, date) and not isinstance(at, datetime):
        return at
    dt = at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def str_day(d: date) -> str:
    return d.isoformat()


class StreakEngine:
    def __init__(self, db: Session, ws: Optional[WSConnectionManager] = None, today: Optional[date] = None):
        self.db = db
        self.ws = ws or WSConnectionManager()
        self.streaks = StreakRepository(db)
        self.days = StreakDayRepository(db)
        self.events = StreakEventRepository(db)
        self._today = today or utc_day(datetime.now(timezone.utc))

    # ------------------------------------------------------------------ #
    # Entry point
    # ------------------------------------------------------------------ #

    async def record_activity(
        self, *, actor_id: str, peer_user_id: str, conversation_id: str, sent_at: datetime
    ) -> None:
        day = utc_day(sent_at)
        self._upsert_qualification(actor_id, conversation_id, day)
        self.db.flush()
        await self._evaluate_dir(actor_id, peer_user_id, conversation_id, day)
        await self._evaluate_dir(peer_user_id, actor_id, conversation_id, day)
        self.db.commit()

    # ------------------------------------------------------------------ #
    # Qualification
    # ------------------------------------------------------------------ #

    def _upsert_qualification(self, user_id: str, conversation_id: str, day: date) -> StreakDayQualification:
        row = self.days.by_day(user_id, conversation_id, day)
        if row is None:
            row = StreakDayQualification(
                user_id=user_id,
                peer_user_id="",
                conversation_id=conversation_id,
                day=day,
                message_count=1,
                first_message_at=datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc),
            )
            self.days.add(row)
        else:
            row.message_count += 1
        return row

    # ------------------------------------------------------------------ #
    # Evaluation
    # ------------------------------------------------------------------ #

    def _has_peer_qualified(self, peer_id: str, conversation_id: str, day: date) -> bool:
        from sqlalchemy import select

        exists = self.db.scalar(
            select(StreakDayQualification.id)
            .where(
                StreakDayQualification.user_id == peer_id,
                StreakDayQualification.conversation_id == conversation_id,
                StreakDayQualification.day == day,
            )
            .limit(1)
        )
        return exists is not None

    async def _evaluate_dir(self, user_id: str, peer_user_id: str, conversation_id: str, day: date) -> None:
        if not self._has_peer_qualified(peer_user_id, conversation_id, day):
            return  # round not yet complete
        streak = self.streaks.by_triple(user_id, peer_user_id, conversation_id)
        if streak is None:
            streak = Streak(
                user_id=user_id,
                peer_user_id=peer_user_id,
                conversation_id=conversation_id,
                current_streak=0,
                longest_streak=0,
            )
            self.streaks.add(streak)
            self.db.flush()

        prev_day = streak.prepared_at
        if prev_day == day:
            self._maybe_emit_milestone(streak)
            return

        if prev_day is None:
            await self._advance(streak, day, event="incremented", meta=f"started on {day}")
        elif day == prev_day + timedelta(days=1):
            await self._advance(streak, day, event="incremented")
        elif day > prev_day + timedelta(days=1):
            gap = (day - prev_day).days - 1
            if self._freeze_covers(streak, gap, user_id):
                s = self.db.get(Streak, streak.id)
                s.current_streak += 1
                s.prepared_at = day
                s.freezes_available -= 1
                await self._emit_event(s, "freeze_used", day, meta=f"covered {gap} missed day(s)")
                self._maybe_emit_milestone(s)
                await self._notify_streak(s)
            else:
                await self._record_broken(streak, day)
                await self._advance(streak, day, event="recovered", meta="restarted after break")
        else:
            # day < prev_day: late/duplicate qualification, already accounted.
            self._maybe_emit_milestone(streak)

    def _freeze_covers(self, streak: Streak, gap: int, user_id: str) -> bool:
        if gap != 1 or streak.freezes_available <= 0:
            return False
        from sqlalchemy import select

        from app.models.user import User

        row = self.db.scalar(select(User.streak_freezes_enabled).where(User.id == user_id))
        return bool(row is not False)

    async def _advance(self, streak: Streak, day: date, *, event: str, meta: Optional[str] = None) -> None:
        s = self.db.get(Streak, streak.id)
        s.current_streak += 1
        s.prepared_at = day
        if s.current_streak > s.longest_streak:
            s.longest_streak = s.current_streak
            s.longest_start_date = day - timedelta(days=s.current_streak - 1)
        await self._emit_event(s, event, day, meta=meta)
        await self._grant_freeze_if_due(s)
        self._maybe_emit_milestone(s)
        await self._notify_streak(s)

    def _record_broken(self, streak: Streak, day: date) -> None:
        s = self.db.get(Streak, streak.id)
        s.current_streak = 0
        self.events.add(
            StreakEvent(
                user_id=s.user_id,
                peer_user_id=s.peer_user_id,
                conversation_id=s.conversation_id,
                event_type="broken",
                day=day,
                streak_after=0,
                meta="broken",
            )
        )

    async def _grant_freeze_if_due(self, streak: Streak) -> None:
        if not settings.streak_freezes_enabled:
            return
        # One freeze every 7 rounds (max 3 held), aligned to pleasant milestones.
        if streak.current_streak > 0 and streak.current_streak % 7 == 0 and streak.freezes_available < 3:
            streak.freezes_available += 1
            await self._emit_event(streak, "freeze_granted", streak.prepared_at or self._today, meta=f"milestone {streak.current_streak}")

    def _maybe_emit_milestone(self, streak: Streak) -> None:
        if streak.current_streak in MILESTONES:
            # Only the one crossing we haven't yet recorded (idempotent via event record).
            if not self._milestone_recorded(streak, streak.current_streak):
                self.events.add(
                    StreakEvent(
                        user_id=streak.user_id,
                        peer_user_id=streak.peer_user_id,
                        conversation_id=streak.conversation_id,
                        event_type="milestone",
                        day=streak.prepared_at or self._today,
                        streak_after=streak.current_streak,
                        meta=f"milestone {streak.current_streak}",
                    )
                )

    def _milestone_recorded(self, streak: Streak, milestone: int) -> bool:
        from sqlalchemy import select

        exists = self.db.scalar(
            select(StreakEvent.id)
            .where(
                StreakEvent.user_id == streak.user_id,
                StreakEvent.peer_user_id == streak.peer_user_id,
                StreakEvent.conversation_id == streak.conversation_id,
                StreakEvent.event_type == "milestone",
                StreakEvent.meta == f"milestone {milestone}",
            )
            .limit(1)
        )
        return exists is not None

    async def _emit_event(self, streak: Streak, event_type: str, day: date, meta: Optional[str]) -> None:
        self.events.add(
            StreakEvent(
                user_id=streak.user_id,
                peer_user_id=streak.peer_user_id,
                conversation_id=streak.conversation_id,
                event_type=event_type,
                day=day,
                streak_after=streak.current_streak,
                meta=meta,
            )
        )

    async def _notify_streak(self, streak: Streak) -> None:
        if self.ws is None:
            return
        envelope = Envelope(
            type=EventType.STREAK_UPDATED,
            conversation_id=streak.conversation_id,
            data={
                "user_id": streak.user_id,
                "current_streak": streak.current_streak,
                "longest_streak": streak.longest_streak,
                "alive": True,
                "last_activity_day": str_day(streak.prepared_at) if streak.prepared_at else None,
            },
        )
        await self.ws.send_to_user(streak.user_id, envelope)
        if streak.current_streak in MILESTONES and self._milestone_recorded(streak, streak.current_streak):
            await self.ws.send_to_user(
                streak.user_id,
                Envelope(
                    type=EventType.STREAK_MILESTONE,
                    conversation_id=streak.conversation_id,
                    data={
                        "milestone": streak.current_streak,
                        "user_id": streak.user_id,
                        "peer_user_id": streak.peer_user_id,
                    },
                ),
            )

    # ------------------------------------------------------------------ #
    # Expiration / reminders (scheduled)
    # ------------------------------------------------------------------ #

    async def expire_stale(self, today: Optional[date] = None) -> int:
        today = today or self._today
        threshold = today - timedelta(days=1)
        banner = 0
        active = self.db.query(Streak).filter(Streak.prepared_at < threshold, Streak.current_streak > 0).all()
        for s in active:
            s.current_streak = 0
            self.events.add(
                StreakEvent(
                    user_id=s.user_id,
                    peer_user_id=s.peer_user_id,
                    conversation_id=s.conversation_id,
                    event_type="broken",
                    day=s.prepared_at or today,
                    streak_after=0,
                    meta="expired",
                )
            )
            banner += 1
        self.db.commit()
        return banner

    def pending_reminders(self, today: Optional[date] = None) -> list[dict]:
        today = today or self._today
        active = self.db.query(Streak).filter(
            Streak.prepared_at.in_([today - timedelta(days=1)]),
            Streak.current_streak > 0,
        ).all()
        return [
            {
                "user_id": s.user_id,
                "peer_user_id": s.peer_user_id,
                "conversation_id": s.conversation_id,
                "current_streak": s.current_streak,
            }
            for s in active
        ]

    # ------------------------------------------------------------------ #
    # Queries (authoritative aggregation for API responses)
    # ------------------------------------------------------------------ #

    def live(self, user_id: str, peer_user_id: str, conversation_id: str) -> dict:
        streak = self.streaks.by_triple(user_id, peer_user_id, conversation_id)
        if streak is None:
            return {
                "user_id": user_id,
                "peer_user_id": peer_user_id,
                "conversation_id": conversation_id,
                "current_streak": 0,
                "longest_streak": 0,
                "longest_start_date": None,
                "prepared_at": None,
                "alive": False,
                "freezes_available": 0,
                "milestones_reached": [],
                "closest_milestone": MILESTONES[0] if MILESTONES else None,
            }
        alive = streak.prepared_at in (self._today, self._today - timedelta(days=1)) and streak.current_streak > 0
        milestones = [m for m in MILESTONES if m <= streak.longest_streak]
        next_ms = next((m for m in MILESTONES if m > streak.current_streak), None)
        return {
            "user_id": streak.user_id,
            "peer_user_id": streak.peer_user_id,
            "conversation_id": streak.conversation_id,
            "current_streak": streak.current_streak,
            "longest_streak": streak.longest_streak,
            "longest_start_date": streak.longest_start_date,
            "prepared_at": streak.prepared_at,
            "alive": alive,
            "freezes_available": streak.freezes_available,
            "milestones_reached": milestones,
            "closest_milestone": next_ms,
        }