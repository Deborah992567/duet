"""Friendship and friend-request service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.constants import FriendshipStatus
from app.core.events import Envelope, EventType
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.repositories.friendship_repo import FriendRequestRepository, FriendshipRepository
from app.repositories.user_repo import BlockRepository, UserRepository
from app.schemas.friend import (
    FriendList,
    FriendRequestPublic,
    FriendSummary,
    MutualConnection,
)
from app.services.base import Service
from app.services.user_service import to_public


class FriendshipService(Service):
    def __init__(self, db: Session, **kwargs):
        super().__init__(db, **kwargs)
        self.requests = FriendRequestRepository(db)
        self.friendships = FriendshipRepository(db)
        self.users = UserRepository(db)
        self.blocks = BlockRepository(db)

    # ------------------------------------------------------------------ #
    # Requests
    # ------------------------------------------------------------------ #

    async def send_request(self, sender_id: str, recipient_id: str, message: Optional[str]) -> FriendRequest:
        if sender_id == recipient_id:
            raise ForbiddenError("You cannot add yourself.")
        target = self.users.get(recipient_id)
        if target is None:
            raise NotFoundError("User not found.")
        if self.blocks.is_blocked(sender_id, recipient_id) or self.blocks.is_blocked(recipient_id, sender_id):
            raise NotFoundError("User not found.")
        if self.friendships.by_users(sender_id, recipient_id) is not None:
            raise ConflictError("You are already friends with this user.", code="already_friends")
        existing = self.requests.pending_between(sender_id, recipient_id)
        if existing:
            raise ConflictError("You already sent a request to this user.", code="request_pending")
        reverse = self.requests.pending_between(recipient_id, sender_id)
        if reverse is not None:
            # Auto-accept the reverse request -> immediate friendship.
            restored = await self.accept_request(recipient_id, reverse.id)
            return reverse

        request = self.requests.add(
            self.requests.model(sender_id=sender_id, recipient_id=recipient_id, message=message)
        )
        self.commit()
        await self.ws.send_to_user(
            recipient_id,
            Envelope(type=EventType.FRIEND_REQUEST_RECEIVED, data={"request_id": request.id}),
        )
        return request

    async def list_incoming(self, user_id: str, limit: int = 50) -> list[FriendRequestPublic]:
        rows = self.requests.received_by(user_id, limit=limit)
        return self._render_requests(rows, user_id)

    async def list_outgoing(self, user_id: str, limit: int = 50) -> list[FriendRequestPublic]:
        rows = self.requests.sent_by(user_id, limit=limit)
        return self._render_requests(rows, user_id)

    async def accept_request(self, user_id: str, request_id: str) -> FriendRequest:
        request = self.requests.get(request_id)
        if request is None or request.recipient_id != user_id:
            raise NotFoundError("Friend request not found.")
        if request.status != FriendshipStatus.PENDING:
            raise ConflictError("This friend request is no longer pending.", code="request_closed")
        if self.friendships.by_users(request.sender_id, request.recipient_id) is not None:
            raise ConflictError("You are already friends.", code="already_friends")

        request.status = FriendshipStatus.ACCEPTED
        request.responded_at = datetime.now(timezone.utc)
        self.friendships.add(
            self.friendships.model(user_a=min(request.sender_id, request.recipient_id),
                                   user_b=max(request.sender_id, request.recipient_id))
        )
        self.commit()
        await self.ws.send_to_user(
            request.sender_id,
            Envelope(type=EventType.FRIEND_REQUEST_RESOLVED,
                     data={"request_id": request.id, "accepted": True}),
        )
        return request

    async def decline_request(self, user_id: str, request_id: str) -> None:
        request = self.requests.get(request_id)
        if request is None or request.recipient_id != user_id:
            raise NotFoundError("Friend request not found.")
        if request.status != FriendshipStatus.PENDING:
            raise ConflictError("This friend request is no longer pending.", code="request_closed")
        request.status = FriendshipStatus.REJECTED
        request.responded_at = datetime.now(timezone.utc)
        self.commit()
        await self.ws.send_to_user(
            request.sender_id,
            Envelope(type=EventType.FRIEND_REQUEST_RESOLVED,
                     data={"request_id": request.id, "accepted": False}),
        )

    async def cancel_request(self, user_id: str, request_id: str) -> None:
        request = self.requests.get(request_id)
        if request is None or request.sender_id != user_id:
            raise NotFoundError("Friend request not found.")
        request.status = FriendshipStatus.REMOVED
        request.responded_at = datetime.now(timezone.utc)
        self.commit()

    # ------------------------------------------------------------------ #
    # Friends
    # ------------------------------------------------------------------ #

    def list_friends(self, user_id: str, limit: int = 50, offset: int = 0) -> FriendList:
        rows = self.friendships.list_for_user(user_id, limit=limit, offset=offset)
        friend_ids = [r.user_b if r.user_a == user_id else r.user_a for r in rows]
        users = {u.id: u for u in self.users.by_ids(friend_ids)}
        online = {i for i in friend_ids if self.ws.is_online(i)}
        items = [
            FriendSummary(
                friendship_id=r.id,
                user=to_public(users[fid], friend_ids={user_id}, online_ids=online),
                created_at=r.created_at,
            )
            for r, fid in zip(rows, friend_ids)
            if fid in users
        ]
        return FriendList(items=items, has_more=len(rows) == limit)

    async def remove_friend(self, user_id: str, target_id: str) -> None:
        friendship = self.friendships.by_users(user_id, target_id)
        if friendship is None:
            raise NotFoundError("You are not friends with this user.")
        friendship.status = FriendshipStatus.REMOVED
        friendship.removed_by = user_id
        friendship.removed_at = datetime.now(timezone.utc)
        self.commit()
        await self.ws.send_to_users(
            [user_id, target_id],
            Envelope(type=EventType.FRIENDSHIP_REMOVED, data={"peer_user_id": target_id}),
        )

    def list_mutual(self, viewer_id: str, peer_id: str, limit: int = 20) -> list[MutualConnection]:
        my_friends = self.friendships.friend_ids_of(viewer_id)
        if peer_id not in my_friends:
            # Only surfaces for connected users to avoid leaking social graphs.
            return []
        peer_friends = self.friendships.friend_ids_of(peer_id)
        mutual_ids = my_friends & peer_friends
        mutual_ids.discard(viewer_id)
        users = {u.id: u for u in self.users.by_ids(sorted(mutual_ids)[:limit])}
        items = [
            MutualConnection(user=to_public(u), mutual_count=min(len(mutual_ids), limit))
            for u in users.values()
        ]
        return items

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def _render_requests(self, rows, viewer_id: str) -> list[FriendRequestPublic]:
        ids = {r.sender_id for r in rows} | {r.recipient_id for r in rows}
        users = {u.id: u for u in self.users.by_ids(list(ids))}

        def render(r) -> FriendRequestPublic:
            return FriendRequestPublic(
                id=r.id,
                sender_id=r.sender_id,
                recipient_id=r.recipient_id,
                status=r.status,
                message=r.message,
                created_at=r.created_at,
                sender=to_public(users[r.sender_id]) if r.sender_id in users else None,
                recipient=to_public(users[r.recipient_id]) if r.recipient_id in users else None,
            )

        return [render(r) for r in rows]