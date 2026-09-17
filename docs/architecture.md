# Architecture

## Backend

```
uvicorn → FastAPI
  ├── /v1/*  REST routes (auth, users, friends, conversations, messages,
  │           streaks, calls, media, notifications, reports)
  └── /v1/ws WebSocket realtime (subscribe / presence / message.created …
                / typing / heartbeat)

SQLAlchemy (MariaDB in prod, SQLite in tests)   Redis (rate limits + pub/sub)
```

### Realtime protocol

1. Client connects with `?token=`.
2. First frame must be `{"type": "subscribe", "conversation_ids": [...]}`.
3. Server replies `subscribed`, then emits `presence.changed` for online peers.
4. Events: `message.created`, `message.updated`, `message.deleted`,
   `receipt.read`, `typing`, `streak.updated`, `heartbeat` / `heartbeat_ack`.

### Dependency discipline

- `app/api/*` routers → `app/services/*` services → `app/models/*` ORM.
- `app/core/timeutil.py` centralizes naive/aware UTC handling.
- `get_current_user_ws(websocket, token)` is called explicitly by WS handlers
  (no FastAPI injection for the socket path).

## iOS

```
SwiftUI + Observation + SwiftData
├── AppState / SessionStore / KeychainStore   auth + session
├── APIClient (URLSession, envelope decoding)
├── RealtimeClient  RawEnvelope + JSONValue WS decode
├── LocalStore      offline cache + outbox (SwiftData)
├── Feature stores  Conversation/Chat/Friends/Streaks/Settings
└── Theme           flat baby-pink + white tokens
```

Offline-first: messages hydrate from SwiftData immediately; failures enqueue to
the outbox and retry on socket reconnect. `URLRequestBuilder` attaches the
Bearer token.

## Calls

Calls are an **architecture seam**: signaling endpoints, a preview UI, and a
hold-to-talk voice-message pipeline exist. RTC media transport activates for
region-approved production hardware.

## Tests

- Backend: 50 pytest tests (in-memory SQLite + fakeredis, `greatest()` UDF
  registered in `conftest.py`).
- iOS: unit tests in `EnvyChatTests` (date alignment, decoding, request builder).