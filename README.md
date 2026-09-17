# EnvyChat

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
.venv/bin/pytest                                 # full suite (50 passing)
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
open EnvyChat.xcodeproj          # iPhone-only target, iOS 17+
```

`API_BASE_URL` env var (Debug) overrides the default `http://127.0.0.1:8000`.

## Design

Flat baby-pink + white palette, no gradients. Tokens in
`ios/EnvyChat/Design/Theme.swift`.

## Pushing

Small, reviewable pushes to `origin master`, one per feature/step.

## More

- [Streak system](docs/streaks.md)
- [API reference](docs/api.md)
- [Architecture](docs/architecture.md)
- [iOS notes](docs/ios.md)