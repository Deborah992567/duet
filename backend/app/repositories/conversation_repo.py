"""Conversation and membership repository."""

from __future__ import annotations

from sqlalchemy import and_, func, or_, select

from app.core.constants import ConversationType, MemberRole
from app.models.conversation import Conversation, ConversationMember
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    @staticmethod
    def direct_key(a: str, b: str) -> str:
        return ":".join(sorted((a, b)))

    def direct_between(self, a: str, b: str) -> Conversation | None:
        return self.db.scalar(
            select(Conversation).where(Conversation.direct_key == self.direct_key(a, b))
        )

    def by_id_with_members(self, conversation_id: str) -> Conversation | None:
        return self.get(conversation_id)

    def list_for_user(
        self, user_id: str, limit: int = 30, before: int | None = None
    ) -> list[Conversation]:
        """Visible conversations ordered by last activity, keyset paginated."""
        sub = (
            select(ConversationMember.conversation_id)
            .where(ConversationMember.user_id == user_id, ConversationMember.is_visible.is_(True))
            .subquery()
        )
        stmt = select(Conversation).where(Conversation.id.in_(select(sub.c.conversation_id)))
        if before is not None:
            stmt = stmt.where(Conversation.updated_at.is_not(None)) if before == 0 else stmt

        # Ordering by last_message_at descending is enough for the inbox.
        stmt = stmt.order_by(Conversation.last_message_at.desc().nullslast(), Conversation.created_at.desc())
        return list(self.db.scalars(stmt.limit(limit)).all())


class ConversationMemberRepository(BaseRepository[ConversationMember]):
    model = ConversationMember

    def member(self, conversation_id: str, user_id: str) -> ConversationMember | None:
        return self.db.scalar(
            select(ConversationMember).where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == user_id,
            )
        )

    def is_member(self, conversation_id: str, user_id: str) -> bool:
        return self.member(conversation_id, user_id) is not None

    def members_of(self, conversation_id: str, include_left: bool = False) -> list[ConversationMember]:
        stmt = select(ConversationMember).where(ConversationMember.conversation_id == conversation_id)
        if not include_left:
            stmt = stmt.where(ConversationMember.left_at.is_(None))
        return list(self.db.scalars(stmt).all())

    def member_ids(self, conversation_id: str) -> list[str]:
        return list(
            self.db.scalars(
                select(ConversationMember.user_id).where(
                    ConversationMember.conversation_id == conversation_id,
                    ConversationMember.left_at.is_(None),
                )
            ).all()
        )

    def member_ids_of_all(self, user_id: str) -> list[str]:
        """All active conversation ids a user participates in."""
        return list(
            self.db.scalars(
                select(ConversationMember.conversation_id).where(
                    ConversationMember.user_id == user_id,
                    ConversationMember.left_at.is_(None),
                    ConversationMember.is_visible.is_(True),
                )
            ).all()
        )

    def role_of(self, conversation_id: str, user_id: str) -> MemberRole | None:
        m = self.member(conversation_id, user_id)
        return m.role if m else None

    def count_members(self, conversation_id: str) -> int:
        return self.count(
            ConversationMember.conversation_id == conversation_id,
            ConversationMember.left_at.is_(None),
        )

    def update_unread(self, conversation_id: str, user_id: str, delta: int = 1) -> None:
        from sqlalchemy import update

        self.db.execute(
            update(ConversationMember)
            .where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == user_id,
            )
            .values(unread_count=func.greatest(0, ConversationMember.unread_count + delta))
        )

    def reset_unread(self, conversation_id: str, user_id: str) -> None:
        from sqlalchemy import update

        self.db.execute(
            update(ConversationMember)
            .where(
                ConversationMember.conversation_id == conversation_id,
                ConversationMember.user_id == user_id,
            )
            .values(unread_count=0)
        )

    def mark_left(self, conversation_id: str, user_id: str) -> None:
        m = self.member(conversation_id, user_id)
        if m:
            from datetime import datetime, timezone

            m.left_at = datetime.now(timezone.utc)
            m.is_visible = False