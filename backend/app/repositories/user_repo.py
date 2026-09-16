"""User, device, and block-list repository."""

from __future__ import annotations

from sqlalchemy import or_, select

from app.models.user import BlockedUser, Device, User, UserProfile
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def by_identifier(self, identifier: str) -> User | None:
        ident = identifier.lstrip("@").strip()
        return self.db.scalar(
            select(User).where(or_(User.username == ident, User.email == identifier))
        )

    def by_ids(self, ids: list[str]) -> list[User]:
        return list(self.db.scalars(select(User).where(User.id.in_(ids))).all())

    def search(self, query: str, limit: int, exclude_id: str) -> list[User]:
        return list(
            self.db.scalars(
                select(User)
                .where(
                    User.id != exclude_id,
                    or_(
                        User.username.ilike(f"%{query}%"),
                        User.email.ilike(f"%{query}%"),
                    ),
                )
                .limit(limit)
            ).all()
        )

    def get_profile(self, user_id: str) -> UserProfile | None:
        return self.db.scalar(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )

    def create_profile(self, user_id: str, display_name: str) -> UserProfile:
        profile = UserProfile(user_id=user_id, display_name=display_name)
        self.add(profile)
        return profile


class DeviceRepository(BaseRepository[Device]):
    model = Device

    def by_user(self, user_id: str, include_revoked: bool = False) -> list[Device]:
        stmt = select(Device).where(Device.user_id == user_id)
        if not include_revoked:
            stmt = stmt.where(Device.revoked_at.is_(None))
        return list(self.db.scalars(stmt).all())

    def by_refresh_hash(self, refresh_hash: str) -> Device | None:
        return self.db.scalar(
            select(Device).where(Device.refresh_token_hash == refresh_hash)
        )

    def revoke_others(self, user_id: str, current_device_id: str) -> int:
        from sqlalchemy import update

        result = self.db.execute(
            update(Device)
            .where(Device.user_id == user_id, Device.id != current_device_id)
            .values(is_current=False)
        )
        return result.rowcount or 0


class BlockRepository(BaseRepository[BlockedUser]):
    model = BlockedUser

    def is_blocked(self, user_id: str, candidate_id: str) -> bool:
        return self.exists(
            BlockedUser.user_id == user_id,
            BlockedUser.blocked_user_id == candidate_id,
        )

    def blocked_ids(self, user_id: str) -> set[str]:
        rows = self.db.scalars(
            select(BlockedUser.blocked_user_id).where(BlockedUser.user_id == user_id)
        ).all()
        return set(rows)

    def block(self, user_id: str, blocked_user_id: str) -> BlockedUser:
        entry = BlockedUser(user_id=user_id, blocked_user_id=blocked_user_id)
        self.add(entry)
        return entry

    def unblock(self, user_id: str, blocked_user_id: str) -> bool:
        row = self.db.scalar(
            select(BlockedUser).where(
                BlockedUser.user_id == user_id,
                BlockedUser.blocked_user_id == blocked_user_id,
            )
        )
        if row is None:
            return False
        self.delete(row)
        return True