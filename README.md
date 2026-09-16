# EnvyChat

**EnvyChat** is an iPhone-only, production-grade private messaging platform with a signature, deterministic **streak system**. It is a serious, polished iOS product backed by a modular FastAPI backend.

> Private messaging + communication + meaningful streaks. Not a Snapchat clone.

---

## Repository layout

```
envychat/
├── backend/        FastAPI + MariaDB + Redis + WebSockets
├── ios/            SwiftUI iPhone app (Xcode project generated via XcodeGen)
└── docs/           Product, API, architecture, privacy & compliance docs
```

## Stack

| Layer    | Technology |
| -------- | ---------- |
| Client   | Swift 6 / SwiftUI / Swift Concurrency / SwiftData / URLSession / WebSockets / CallKit / AVFoundation / Photos |
| API      | FastAPI (Python) |
| Database | MariaDB (SQLAlchemy ORM, clean data-access layer for later migration) |
| Cache/RT | Redis (presence, typing, WS coordination, rate limiting, queues) |
| Media    | Object storage (S3-compatible) |
| Notifications | APNs |

## Principles

- Backend is the **source of truth** for streak calculations.
- **No fake real-time**: WebSockets, not polling.
- **Offline-first** client: local persistence, pending queue, retry, sync.
- Centralized design-token theme system (light/dark/system), **no gradients anywhere**.
- Every visible feature either works or is explicitly marked not implemented.

## Docs

- [Product specification](docs/product-spec.md)
- [API contract](docs/api.md)
- [Real-time event contract](docs/events.md)
- [Streak engine spec](docs/streaks.md)
- [Database schema](docs/database.md)
- [iOS architecture](docs/ios-architecture.md)
- [Security & privacy](docs/security-privacy.md)

## Quickstart (backend)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d maria redis     # or reuse a local MariaDB / Redis
alembic upgrade head
uvicorn app.main:app --reload
```

Run the test suite:

```bash
pytest
```

## Quickstart (iOS)

```bash
cd ios
xcodegen generate
xcodebuild -scheme EnvyChat -destination 'platform=iOS Simulator,name=iPhone 17 Pro' build
```