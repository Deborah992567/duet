"""User profile, search, visibility, and block management service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.user import BlockedUser, User, UserProfile
from app.repositories.user_repo import BlockRepository, DeviceRepository, UserRepository
from app.schemas.user import BlockedUserPublic, UpdateProfileRequest, UserPublic, UserSearchResult
from app.services.base import Service

DROP_FIELDS = ("password_hash",)


def to_public(
    user: User,
    *,
    friend_ids: Optional[set[str]] = None,
    blocked_by_me: Optional[set[str]] = None,
    online_ids: Optional[set[str]] = None,
) -> UserPublic:
    friend_ids = friend_ids or set()
    blocked_by_me = blocked_by_me or set()
    online_ids = online_ids or set()
    return UserPublic(
        id=user.id,
        username=user.username,
        display_name=user.profile.display_name if user.profile else user.username,
        avatar_url=user.profile.avatar_url if user.profile else None,
        bio=user.profile.bio if user.profile else "",
        status=user.status,
        is_friend=user.id in friend_ids,
        is_blocked=user.id in blocked_by_me,
        online=user.id in online_ids,
        last_seen_at=user.last_seen_at,
        streak_visible=user.streak_visible,
    )


class UserService(Service):
    def __init__(self, db: Session, **kwargs):
        super().__init__(db, **kwargs)
        self.users = UserRepository(db)
        self.blocks = BlockRepository(db)
        self.devices = DeviceRepository(db)

    # ------------------------------------------------------------------ #
    # Me / profile
    # ------------------------------------------------------------------ #

    def get_me(self, user_id: str) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    def update_profile(self, user_id: str, payload: UpdateProfileRequest) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        profile = user.profile
        if payload.display_name is not None:
            profile.display_name = payload.display_name
        if payload.bio is not None:
            profile.bio = payload.bio
        if payload.username is not None and payload.username != user.username:
            if self.users.by_username(payload.username):
                raise ConflictError("That username is already taken.", code="username_taken")
            user.username = payload.username
        if payload.avatar_url is not None:
            profile.avatar_url = str(payload.avatar_url)
        if payload.phone is not None:
            profile.phone = payload.phone
        if payload.theme is not None:
            user.theme = payload.theme
        if payload.locale is not None:
            user.locale = payload.locale
        if payload.timezone is not None:
            user.timezone = payload.timezone
        self.commit()
        return user

    # ------------------------------------------------------------------ #
    # Search / profile visibility
    # ------------------------------------------------------------------ #

    def search_users(self, caller_id: str, query: str, limit: int = 20) -> UserSearchResult:
        q = query.strip().lstrip("@")
        if len(q) < 2:
            return UserSearchResult(items=[])
        friend_ids = self._friend_lookup(caller_id)
        blocked = self.blocks.blocked_ids(caller_id)
        online = set()
        results = self.users.search(q, limit + 1, exclude_id=caller_id)
        items = [
            to_public(u, friend_ids=friend_ids, blocked_by_me=blocked, online_ids=online)
            for u in results[:limit]
        ]
        return UserSearchResult(items=items, has_more=len(results) > limit)

    def get_user_public(self, caller_id: str, target_id: str) -> UserPublic:
        target = self.users.get(target_id)
        if target is None or (target.status.value == "deleted"):
            raise NotFoundError("User not found.")
        if caller_id != target_id and self.blocks.is_blocked(target_id, caller_id):
            raise NotFoundError("User not found.")
        if caller_id != target_id and target.profile_visibility == "nobody":
            raise NotFoundError("User not found.")
        if caller_id != target_id and target.profile_visibility == "friends":
            friend_ids = self._friend_lookup(caller_id)
            if target_id not in friend_ids:
                raise NotFoundError("User not found.")
        friend_ids = self._friend_lookup(caller_id)
        blocked = self.blocks.blocked_ids(caller_id)
        online_ids = self._online_ids([target_id])
        return to_public(target, friend_ids=friend_ids, blocked_by_me=blocked, online_ids=online_ids)

    # ------------------------------------------------------------------ #
    # Blocking / unblocking
    # ------------------------------------------------------------------ #

    async def block_user(self, caller_id: str, user_id: str, also_remove_as_friend: bool = True) -> None:
        if caller_id == user_id:
            raise ForbiddenError("You cannot block yourself.")
        target = self.users.get(user_id)
        if target is None:
            raise NotFoundError("User not found.")
        if not self.blocks.is_blocked(caller_id, user_id):
            self.blocks.block(caller_id, user_id)
        if also_remove_as_friend:
            self._break_friendship(caller_id, user_id)
        self.flush()
        encrypted_conversations = self._close_direct_conversations(caller_id, user_id)
        for cid in encrypted_conversations:
            self.ws.leave_room(caller_id, cid)
        self.commit()

    async def unblock_user(self, caller_id: str, user_id: str) -> None:
        self.blocks.unblock(caller_id, user_id)
        self.commit()

    def list_blocked(self, caller_id: str, limit: int = 50) -> list[BlockedUserPublic]:
        rows = self.db.scalars(
            select(BlockedUser)
            .where(BlockedUser.user_id == caller_id)
            .order_by(BlockedUser.created_at.desc())
            .limit(limit)
        ).all()
        targets = {b.blocked_user_id: b for b in rows}
        users = {u.id: u for u in self.users.by_ids(list(targets))}
        return [
            BlockedUserPublic(
                id=b.blocked_user_id,
                blocked_at=b.created_at,
                user=to_public(users[b.blocked_user_id]) if b.blocked_user_id in users else None,
            )
            for b in rows
        ]

    # ------------------------------------------------------------------ #
    # Privacy/settings
    # ------------------------------------------------------------------ #

    def update_privacy(self, user_id: str, *, read_receipts: Optional[bool] = None,
                       show_online: Optional[bool] = None, visibility: Optional[str] = None,
                       allow_preview: Optional[bool] = None) -> User:
        user = self.users.get(user_id)
        if visibility is not None and visibility not in ("everyone", "friends", "nobody"):
            raise ForbiddenError("Invalid privacy visibility.")
        if read_receipts is not None:
            user.read_receipts_enabled = read_receipts
        if show_online is not None:
            user.show_online_status = show_online
        if visibility is not None:
            user.profile_visibility = visibility
        if allow_preview is not None:
            user.notification_preview_allowed = allow_preview
        self.commit()
        return user

    def touch_last_seen(self, user_id: str) -> None:
        user = self.users.get(user_id)
        if user:
            user.last_seen_at = datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _friend_lookup(self, user_id: str) -> set[str]:
        from app.repositories.friendship_repo import FriendshipRepository

        return FriendshipRepository(self.db).friend_ids_of(user_id)

    def _break_friendship(self, a: str, b: str) -> None:
        from app.core.constants import FriendshipStatus
        from app.models.friendship import Friendship

        from app.repositories.friendship_repo import pair_ids

        ua, ub = pair_ids(a, b)
        row = self.db.scalar(
            select(Friendship).where(Friendship.user_a == ua, Friendship.user_b == ub)
        )
        if row and row.status != FriendshipStatus.BLOCKED:
            row.status = FriendshipStatus.BLOCKED
            row.removed_by = a
            row.removed_at = datetime.now(timezone.utc)

    def _close_direct_conversations(self, a: str, b: str) -> list[str]:
        from app.core.constants import ConversationType
        from app.models.conversation import Conversation, ConversationMember

        from app.repositories.conversation_repo import ConversationRepository

        key = ConversationRepository.direct_key(a, b)
        conv = self.db.scalar(select(Conversation).where(Conversation.direct_key == key))
        if conv is None:
            return []
        members = self.db.scalars(
            select(ConversationMember).where(
                ConversationMember.conversation_id == conv.id, ConversationMember.left_at.is_(None)
            )
        ).all()
        for m in members:
            m.is_visible = False
            m.left_at = datetime.now(timezone.utc)
        return [conv.id]

    def _online_ids(self, ids: list[str]) -> set[str]:
        return {i for i in ids if self.ws.is_online(i)}