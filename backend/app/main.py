"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, calls, conversations, friends, media, messages, notifications, reports, streaks, users
from app.api.deps import get_ws_manager
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.events import Envelope
from app.core.logging import configure_logging, get_logger
from app.core.redis_client import close_redis, get_redis
from app.db.session import Base, SessionLocal, engine
from app.ws.manager import WSConnectionManager

logger = get_logger(__name__)


def create_app() -> FastAPI:
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.session_factory = SessionLocal
        if settings.environment == "test" or settings.database_url.startswith("sqlite"):
            Base.metadata.create_all(bind=engine)
        redis = get_redis()
        logger.info("EnvyChat API started (env=%s)", settings.environment)
        yield
        await close_redis()

    app = FastAPI(
        title="EnvyChat API",
        version="1.0.0",
        description="Private messaging platform with the EnvyChat streak system.",
        lifespan=lifespan,
    )
    app.state.session_factory = SessionLocal

    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[] if "*" in settings.allowed_hosts else settings.allowed_hosts,
        allow_origin_regex=r".*" if "*" in settings.allowed_hosts else None,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    prefix = settings.api_prefix
    app.include_router(users.router, prefix=prefix)
    app.include_router(auth.router, prefix=prefix)
    app.include_router(friends.router, prefix=prefix)
    app.include_router(conversations.router, prefix=prefix)
    app.include_router(messages.router, prefix=prefix)
    app.include_router(media.router, prefix=prefix)
    app.include_router(streaks.router, prefix=prefix)
    app.include_router(notifications.router, prefix=prefix)
    app.include_router(calls.router, prefix=prefix)
    app.include_router(reports.router, prefix=prefix)
    app.include_router(reports.settings_router, prefix=prefix)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": settings.app_name, "env": settings.environment}

    app.add_api_websocket_route(prefix + "/ws", websocket_endpoint, name="realtime")

    return app


async def websocket_endpoint(websocket: WebSocket) -> None:
    """Real-time event socket.

    Auth via `?token=<access_token>`. The client sends a `subscribe` message on
    connect (list of conversation ids) and then only receives envelopes.
    """
    manager: WSConnectionManager = get_ws_manager()
    user = None
    try:
        from app.api.deps import get_current_user_ws

        user = await get_current_user_ws(websocket)
        user_id = user.id

        await manager.connect(user_id, [], websocket)

        # First inbound message must be the subscription payload.
        subscription = await websocket.receive_json()
        conversation_ids = [
            str(cid) for cid in (subscription.get("conversation_ids") or [])[:200]
        ]
        await websocket.send_json({"type": "subscribed", "conversation_ids": conversation_ids})
        for cid in conversation_ids:
            manager.join_room(user_id, cid)
        await manager.send_to_user(
            user_id,
            Envelope(type="presence.changed", data={"user_id": user_id, "status": "online"}),
        )

        while True:
            message = await websocket.receive_json()
            await _route_client_message(websocket, user_id, message)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 - connection-level errors must not break the pool
        logger.warning("websocket error", exc_info=True)
    finally:
        if user is not None:
            await manager.disconnect(user.id, websocket)


async def _route_client_message(websocket: WebSocket, user_id: str, message: dict) -> None:
    """Handle client-originated ephemeral signals (heartbeat, typing, receipts)."""
    kind = message.get("type")
    manager: WSConnectionManager = get_ws_manager()
    if kind == "heartbeat":
        await manager.set_presence(user_id, "online")
        await websocket.send_json({"type": "heartbeat_ack"})
        return
    if kind == "typing.started":
        cid = message.get("conversation_id")
        from app.services.message_service import MessageService

        service = MessageService(SessionLocal(), redis=manager._redis, ws=manager)
        await service.typing_started(user_id, cid)
        service.db.close()
        return
    if kind == "typing.stopped":
        cid = message.get("conversation_id")
        from app.services.message_service import MessageService

        service = MessageService(SessionLocal(), redis=manager._redis, ws=manager)
        await service.typing_stopped(user_id, cid)
        service.db.close()
        return
    if kind == "receipts.read":
        cid = message.get("conversation_id")
        up_to = message.get("up_to_message_id")
        from app.services.message_service import MessageService

        service = MessageService(SessionLocal(), redis=manager._redis, ws=manager)
        await service.mark_read(user_id, cid, up_to)
        service.db.close()
        return
    if kind == "subscribe":
        for cid in (message.get("conversation_ids") or []):
            manager.join_room(user_id, str(cid))
        await websocket.send_json({"type": "subscribed", "conversation_ids": message.get("conversation_ids")})
        return
    await websocket.send_json({"type": "error", "data": {"code": "unsupported_client_event"}})


app = create_app()