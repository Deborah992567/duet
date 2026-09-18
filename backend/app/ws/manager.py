"""WebSocket connection registry and real-time event bus.

Single-process connection registry. For horizontal scale the bus is designed to
forward envelopes through a Redis pub/sub channel (`duet:events`).
Presence and typing state live in Redis with short TTLs; presence is a
best-effort realtime signal derived from WS heartbeats, never authoritative.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import WebSocket
from redis.asyncio import Redis

from app.core.events import Envelope
from app.core.logging import get_logger

logger = get_logger(__name__)

PRESENCE_PREFIX = "presence"
TYPING_PREFIX = "typing"
EVENT_CHANNEL = "duet:events"

PRESENCE_TTL = 30
TYPING_TTL = 15


class WSConnectionManager:
    def __init__(self, redis: Optional[Redis] = None) -> None:
        self._redis = redis
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        self._conversation_rooms: dict[str, set[str]] = defaultdict(set)
        self._user_rooms: dict[str, set[str]] = defaultdict(set)

    async def connect(self, user_id: str, conversation_ids: list[str], ws: WebSocket) -> None:
        await ws.accept()
        self._connections[user_id].append(ws)
        for cid in conversation_ids:
            self._conversation_rooms[cid].add(user_id)
            self._user_rooms[user_id].add(cid)
        await self.set_presence(user_id, "online")

    async def disconnect(self, user_id: str, ws: WebSocket) -> None:
        sockets = self._connections.get(user_id, [])
        if ws in sockets:
            sockets.remove(ws)
        if not sockets:
            self._connections.pop(user_id, None)
            self._user_rooms.pop(user_id, None)
            await self.set_presence(user_id, "offline")

    def join_room(self, user_id: str, conversation_id: str) -> None:
        self._conversation_rooms[conversation_id].add(user_id)
        self._user_rooms[user_id].add(conversation_id)

    def leave_room(self, user_id: str, conversation_id: str) -> None:
        room = self._conversation_rooms.get(conversation_id)
        if room:
            room.discard(user_id)
        rooms = self._user_rooms.get(user_id)
        if rooms:
            rooms.discard(conversation_id)

    def is_online(self, user_id: str) -> bool:
        return bool(self._connections.get(user_id))

    async def set_presence(self, user_id: str, status: str) -> None:
        if self._redis is None:
            return
        ttl = PRESENCE_TTL if status == "online" else 3600
        payload = {"status": status, "at": datetime.now(timezone.utc).isoformat()}
        try:
            await self._redis.set(f"{PRESENCE_PREFIX}:{user_id}", json.dumps(payload), ex=ttl)
        except Exception:  # pragma: no cover
            logger.warning("presence write failed")

    async def get_presence(self, user_id: str) -> dict | None:
        if self._redis is None:
            return {"status": "online" if self.is_online(user_id) else "offline"}
        try:
            raw = await self._redis.get(f"{PRESENCE_PREFIX}:{user_id}")
        except Exception:  # pragma: no cover
            return None
        return json.loads(raw) if raw else None

    async def set_typing(self, user_id: str, conversation_id: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.set(
                f"{TYPING_PREFIX}:{conversation_id}:{user_id}",
                datetime.now(timezone.utc).isoformat(),
                ex=TYPING_TTL,
            )
        except Exception:  # pragma: no cover
            logger.warning("typing write failed")

    async def clear_typing(self, user_id: str, conversation_id: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.delete(f"{TYPING_PREFIX}:{conversation_id}:{user_id}")
        except Exception:  # pragma: no cover
            pass

    async def send_to_user(self, user_id: str, envelope: Envelope) -> None:
        payload = envelope.model_dump_json()
        for ws in list(self._connections.get(user_id, [])):
            try:
                await ws.send_text(payload)
            except Exception:
                pass

    async def send_to_users(self, user_ids: list[str], envelope: Envelope) -> None:
        for uid in set(user_ids):
            await self.send_to_user(uid, envelope)
        if self._redis is not None and user_ids:
            try:
                await self._redis.publish(
                    EVENT_CHANNEL,
                    json.dumps({"targets": list(set(user_ids)), "envelope": envelope.model_dump()}),
                )
            except Exception:  # pragma: no cover
                logger.warning("event publish failed")

    async def broadcast_to_conversation(self, conversation_id: str, envelope: Envelope) -> None:
        member_ids = list(self._conversation_rooms.get(conversation_id, set()))
        if member_ids:
            await self.send_to_users(member_ids, envelope)