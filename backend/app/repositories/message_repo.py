"""Message, receipt, reaction, attachment, edit, and deletion repositories."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update

from app.core.constants import MessageServerStatus
from app.models.message import (
    Message,
    MessageAttachment,
    MessageDeletion,
    MessageEdit,
    MessageReaction,
    MessageReceipt,
)
from app.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message]):
    model = Message

    def max_server_id(self, conversation_id: str) -> int:
        from sqlalchemy import func

        value = self.db.scalar(
            select(func.max(Message.server_id)).where(Message.conversation_id == conversation_id)
        )
        return int(value) if value else 0

    def by_client_id(self, conversation_id: str, client_id: str) -> Message | None:
        return self.db.scalar(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.client_id == client_id,
            )
        )

    def by_server_range(
        self, conversation_id: str, after_server_id: int | None = None, limit: int = 50
    ) -> list[Message]:
        stmt = select(Message).where(Message.conversation_id == conversation_id)
        if after_server_id is not None:
            stmt = stmt.where(Message.server_id > after_server_id)
        stmt = stmt.order_by(Message.server_id.asc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def before(self, conversation_id: str, before_server_id: int, limit: int = 30) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id, Message.server_id < before_server_id)
            .order_by(Message.server_id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def search(self, conversation_id: str, query: str, limit: int = 30) -> list[Message]:
        stmt = (
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.body.is_not(None),
                Message.body.ilike(f"%{query}%"),
            )
            .order_by(Message.server_id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())

    def global_search(self, user_id: str, conversation_ids: list[str], query: str, limit: int = 30) -> list[Message]:
        if not conversation_ids:
            return []
        stmt = (
            select(Message)
            .where(
                Message.conversation_id.in_(conversation_ids),
                Message.body.is_not(None),
                Message.body.ilike(f"%{query}%"),
            )
            .order_by(Message.server_id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(stmt).all())


class ReceiptRepository(BaseRepository[MessageReceipt]):
    model = MessageReceipt

    def for_message(self, message_id: str) -> list[MessageReceipt]:
        return list(
            self.db.scalars(select(MessageReceipt).where(MessageReceipt.message_id == message_id)).all()
        )

    def mark_delivered(self, message_id: str, user_id: str, conversation_id: str) -> MessageReceipt | None:
        receipt = self.db.scalar(
            select(MessageReceipt).where(
                MessageReceipt.message_id == message_id, MessageReceipt.user_id == user_id
            )
        )
        now = datetime.now(timezone.utc)
        if receipt is None:
            receipt = MessageReceipt(
                message_id=message_id, user_id=user_id, conversation_id=conversation_id, received_at=now
            )
            self.add(receipt)
        elif receipt.received_at is None:
            receipt.received_at = now
        return receipt

    def mark_read(self, message_id: str, user_id: str) -> MessageReceipt | None:
        receipt = self.db.scalar(
            select(MessageReceipt).where(
                MessageReceipt.message_id == message_id, MessageReceipt.user_id == user_id
            )
        )
        if receipt is None:
            return None
        if receipt.read_at is None:
            from datetime import datetime, timezone

            receipt.read_at = datetime.now(timezone.utc)
        return receipt


class ReactionRepository(BaseRepository[MessageReaction]):
    model = MessageReaction

    def for_message(self, message_id: str) -> list[MessageReaction]:
        return list(
            self.db.scalars(
                select(MessageReaction).where(MessageReaction.message_id == message_id).order_by(MessageReaction.created_at)
            ).all()
        )

    def by_user(self, message_id: str, user_id: str, emoji: str) -> MessageReaction | None:
        return self.db.scalar(
            select(MessageReaction).where(
                MessageReaction.message_id == message_id,
                MessageReaction.user_id == user_id,
                MessageReaction.emoji == emoji,
            )
        )


class AttachmentRepository(BaseRepository[MessageAttachment]):
    model = MessageAttachment


class EditRepository(BaseRepository[MessageEdit]):
    model = MessageEdit


class DeletionRepository(BaseRepository[MessageDeletion]):
    model = MessageDeletion

    def deleted_for(self, message_id: str, user_id: str) -> MessageDeletion | None:
        return self.db.scalar(
            select(MessageDeletion).where(
                MessageDeletion.message_id == message_id,
                MessageDeletion.deleted_by == user_id,
                MessageDeletion.delete_for == "me",
            )
        )