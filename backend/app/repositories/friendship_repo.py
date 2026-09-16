"""Friendship and friend request repository."""

from __future__ import annotations

from sqlalchemy import and_, or_, select

from app.core.constants import FriendshipStatus
from app.models.friendship import FriendRequest, Friendship
from app.repositories.base import BaseRepository

_PAIR = lambda a, b: (a, b) if a < b else (b, a)  # noqa: E731


def pair_ids(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


class FriendshipRepository(BaseRepository[Friendship]):
    model = Friendship

    def by_users(self, a: str, b: str) -> Friendship | None:
        ua, ub = pair_ids(a, b)
        return self.db.scalar(
            select(Friendship).where(
                Friendship.user_a == ua, Friendship.user_b == ub, Friendship.status == FriendshipStatus.ACCEPTED
            )
        )

    def friend_ids_of(self, user_id: str) -> set[str]:
        rows = self.db.scalars(
            select(Friendship).where(
                or_(Friendship.user_a == user_id, Friendship.user_b == user_id),
                Friendship.status == FriendshipStatus.ACCEPTED,
            )
        ).all()
        result: set[str] = set()
        for f in rows:
            result.add(f.user_b if f.user_a == user_id else f.user_a)
        return result

    def list_for_user(self, user_id: str, limit: int = 50, offset: int = 0) -> list[Friendship]:
        return list(
            self.db.scalars(
                select(Friendship)
                .where(
                    or_(Friendship.user_a == user_id, Friendship.user_b == user_id),
                    Friendship.status == FriendshipStatus.ACCEPTED,
                )
                .order_by(Friendship.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )

    def mutual_with(self, user_id: str, limit: int = 20) -> list[str]:
        mine = self.friend_ids_of(user_id)
        if not mine:
            return []
        rows = self.db.scalars(
            select(Friendship).where(
                or_(
                    and_(Friendship.user_a.in_(list(mine)), Friendship.user_b == user_id),
                    and_(Friendship.user_b.in_(list(mine)), Friendship.user_a == user_id),
                ),
                Friendship.status == FriendshipStatus.ACCEPTED,
            )
        ).all()
        ids = {f.user_b if f.user_a == user_id else f.user_a for f in rows}
        return sorted(ids)[:limit]


class FriendRequestRepository(BaseRepository[FriendRequest]):
    model = FriendRequest

    def pending_between(self, sender_id: str, recipient_id: str) -> FriendRequest | None:
        return self.db.scalar(
            select(FriendRequest).where(
                FriendRequest.sender_id == sender_id,
                FriendRequest.recipient_id == recipient_id,
                FriendRequest.status == FriendshipStatus.PENDING,
            )
        )

    def received_by(self, user_id: str, limit: int = 50, offset: int = 0) -> list[FriendRequest]:
        return list(
            self.db.scalars(
                select(FriendRequest)
                .where(
                    FriendRequest.recipient_id == user_id,
                    FriendRequest.status == FriendshipStatus.PENDING,
                )
                .order_by(FriendRequest.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )

    def sent_by(self, user_id: str, limit: int = 50, offset: int = 0) -> list[FriendRequest]:
        return list(
            self.db.scalars(
                select(FriendRequest)
                .where(
                    FriendRequest.sender_id == user_id,
                    FriendRequest.status == FriendshipStatus.PENDING,
                )
                .order_by(FriendRequest.created_at.desc())
                .limit(limit)
                .offset(offset)
            ).all()
        )