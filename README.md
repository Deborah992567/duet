# Duet

A baby-pink-and-white messaging app built around a double-sided
**streak** mechanic: both people must send at least one message on the same
calendar day, or the streak dies.

## Repository layout

```
backend/   FastAPI + SQLAlchemy + Redis (+ WebSocket realtime), pytest suite
ios/       SwiftUI iPhone app (xcodegen), offline-first SwiftData cache
docs/      Architecture, streak rules, API reference, iOS notes
```

## Quick start (backend)

```bash
cd backend
python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload          # http://127.0.0.1:8000
.venv/bin/pytest                                 # full suite (54 passing)
```

Run like production (MariaDB + Redis + schema) with:

```bash
cd backend
docker compose up -d                              # MariaDB 11.4 + Redis 7.4
cp .env.example .env                              # configure DATABASE_URL
.venv/bin/alembic upgrade head                    # apply migrations
```

## iOS app

```bash
cd ios
xcodegen generate
open Duet.xcodeproj          # iPhone-only target, iOS 17+
```

`API_BASE_URL` env var (Debug) overrides the default `http://127.0.0.1:8000`.

### What's in the app

- **Inbox** with conversation rows, unread badges, typing + online-presence dots.
- **Chat** with text, images (PhotosPicker) and tap-to-talk voice messages,
  quote replies, forwarding, message search, reactions (react/un-react),
  edit/delete, read receipts and streak banner.
- **Streaks** leaderboard, animated flame detail with live stats, last-30-days
  history strip and milestone progress.
- **Calls** architecture tab with real call-history feed.
- **Friends** (People) with requests, search, add/respond, profiles.
- **Notifications**: in-app feed plus per-channel preferences on Profile.
- **Profile**: streak toggles, notification prefs, sign out, clear local cache.
- Offline-first SwiftData cache with outbox retry, first-run onboarding,
  push-authorization seam, 19 iOS unit tests.

## Design

Flat baby-pink + white palette, no gradients. Tokens in
`ios/Duet/Design/Theme.swift`.

## Pushing

Small, reviewable pushes to `origin master`, one per feature/step.

## More

- [Streak system](docs/streaks.md)
- [API reference](docs/api.md)
- [Architecture](docs/architecture.md)
- [iOS notes](docs/ios.md)