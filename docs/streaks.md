# Streaks

## Rules

- A **streak day** is counted when **both** conversation members send at least
  one message within the same UTC calendar day.
- Messages from either side contribute; score is always `min(a, b)` over
  contiguous aligned days.
- Missing a day (**no message from a side by midnight UTC**) breaks the streak
  back to 0.
- The streak snapshots on `conversations` and `conversations/{id}` as
  `current_streak` + `streak_alive`.

## Lifecycle

| State | Meaning |
| --- | --- |
| `current_streak == 0` | Nothing yet |
| `streak_alive` true | Today already has activity from at least one side |
| `streak_alive` false | Today has no activity yet — a message now counts |

## Engine

`backend/app/services/streak_engine.py` exposes:

- `record_activity(actor_id, peer_user_id, conversation_id, sent_at)` — called
  on every send; updates the aligned-day counters atomically under lock.
- `expire_stale(today=)` — run daily (or on demand) to zero out broken streaks.
- `stats_for(user_id)` — totals used by the app.

Unit-tested in `backend/tests/test_streaks.py`.

## App UI

- Streaks tab: leaderboard of live streaks, sorted by length.
- Chat: flame banner opens an animated detail (milestones 7/30/100/365/500/1000).
- Profile → Streak preferences: visibility, notifications, reminders, freezes.