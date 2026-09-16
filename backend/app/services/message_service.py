"""Message service: sending, delivery/read receipts, reactions, edits, deletes, search."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import (
    MAX_MESSAGE_ATTACHMENTS,
    MessageKind,
    MessageServerStatus,
)
from app.core.events import Envelope, EventType
from app.core.errors import ForbiddenError, NotFoundError, ValidationAppError
from app.models.message import (
    Message,
    MessageAttachment,
    MessageReaction,
    MessageReceipt,
)
from app.repositories.conversation_repo import ConversationMemberRepository, ConversationRepository
from app.repositories.message_repo import (
    AttachmentRepository,
    DeletionRepository,
    EditRepository,
    MessageRepository,
    ReactionRepository,
    ReceiptRepository,
)
from app.repositories.user_repo import UserRepository
from app.schemas.message import (
    EditMessagePayload,
    MessageList,
    MessageOut,
    SendMessagePayload,
    SendMessageResult,
)
from app.services.base import Service
from app.services.streak_engine import StreakEngine


class MessageService(Service):
    def __init__(self, db: Session, **kwargs):
        super().__init__(db, **kwargs)
        self.messages = MessageRepository(db)
        self.receipts = ReceiptRepository(db)
        self.reactions = ReactionRepository(db)
        self.attachments = AttachmentRepository(db)
        self.edits = EditRepository(db)
        self.deletions = DeletionRepository(db)
        self.members = ConversationMemberRepository(db)
        self.conversations = ConversationRepository(db)
        self.users = UserRepository(db)

    # ------------------------------------------------------------------ #
    # Sending
    # ------------------------------------------------------------------ #

    async def send(self, actor_id: str, payload: SendMessagePayload) -> SendMessageResult:
        member = self._require_active_member(actor_id, payload.conversation_id)
        conv = self.conversations.get(payload.conversation_id)
        if conv:
            if conv.admin_only_messaging and self.members.role_of(conv.id, actor_id).value == "member":
                raise ForbiddenError("Only admins can send messages in this group.", code="admin_only")
            if conv.type.value == "direct" and len(payload.attachments) > MAX_MESSAGE_ATTACHMENTS:
                raise ValidationAppError(f"Too many attachments (max {MAX_MESSAGE_ATTACHMENTS}).", code="too_many_attachments")

        # Duplicate prevention: client retries must not double-send.
        if payload.client_id:
            dup = self.messages.by_client_id(payload.conversation_id, payload.client_id)
            if dup is not None:
                return SendMessageResult(message=self._to_out(dup), client_id=payload.client_id)

        if not payload.body and not payload.attachments and payload.kind != MessageKind.EMOJI:
            raise ValidationAppError("A message must contain text or media.", code="empty_message")

        next_server = self.messages.max_server_id(payload.conversation_id) + 1
        now = datetime.now(timezone.utc)
        message = Message(
            conversation_id=payload.conversation_id,
            sender_id=actor_id,
            kind=payload.kind,
            body=payload.body,
            client_id=payload.client_id,
            client_sequence=payload.client_sequence,
            reply_to_message_id=payload.reply_to_message_id,
            server_id=next_server,
            sent_at=now,
            metadata_json=payload.metadata,
        )
        self.messages.add(message)
        self.flush()

        for a in payload.attachments:
            self.attachments.add(
                MessageAttachment(
                    message_id=message.id,
                    kind=a.kind,
                    url=f"/v1/media/{a.upload_id}/content",
                    thumb_url=None,
                    size_bytes=a.size_bytes,
                    duration_ms=a.duration_ms,
                    width=a.width,
                    height=a.height,
                    file_name=a.file_name,
                    waveform=a.waveform,
                )
            )
        self.db.flush()

        # Sender receipt (delivered+read for self).
        self.receipts.mark_delivered(message.id, actor_id, payload.conversation_id)
        sent = self.receipts.mark_read(message.id, actor_id)
        if conv:
            conv.last_message_at = now

        # Unread counters for every other member (best-effort; server-based).
        recipients = [m.user_id for m in self.members.members_of(payload.conversation_id) if m.user_id != actor_id]
        for uid in recipients:
            self.members.update_unread(payload.conversation_id, uid, delta=1)

        self.commit()

        out = self._to_out(message)
        await self.ws.send_to_users(
            recipients,
            Envelope(
                type=EventType.MESSAGE_CREATED,
                conversation_id=payload.conversation_id,
                data={"message": out.model_dump(), "client_id": payload.client_id},
            ),
        )
        # Streak qualification is sourced from persisted server state (backend authoritative).
        if conv and conv.type.value == "direct":
            await self._evaluate_streak(actor_id, payload.conversation_id, now)

        return SendMessageResult(message=out, client_id=payload.client_id)

    # ------------------------------------------------------------------ #
    # Receipts
    # ------------------------------------------------------------------ #

    async def confirm_delivery(self, user_id: str, conversation_id: str, message_ids: list[str]) -> None:
        member = self._require_active_member(user_id, conversation_id)
        confirmed: list[str] = []
        for mid in message_ids:
            message = self.messages.get(mid)
            if message is None or message.conversation_id != conversation_id:
                continue
            self.receipts.mark_delivered(mid, user_id, conversation_id)
            confirmed.append(mid)
        self.commit()
        if confirmed:
            await self.ws.send_to_users(
                [user_id],
                Envelope(type=EventType.MESSAGE_DELIVERED, conversation_id=conversation_id,
                         data={"message_ids": confirmed, "user_id": user_id}),
            )

    async def mark_read(self, user_id: str, conversation_id: str, up_to_message_id: Optional[str]) -> None:
        member = self._require_active_member(user_id, conversation_id)
        if up_to_message_id:
            message = self.messages.get(up_to_message_id)
            if message is None or message.conversation_id != conversation_id:
                raise NotFoundError("Message not found.")
        self.members.reset_unread(conversation_id, user_id)
        read_ids = []
        if up_to_message_id:
            target = self.messages.get(up_to_message_id)
            candidates = self.messages.by_server_range(conversation_id, limit=100_000)
            for m in candidates:
                if m.server_id <= target.server_id and m.sender_id != user_id:
                    receipt = self.receipts.mark_read(m.id, user_id)
                    if receipt is not None and receipt.read_at is not None:
                        read_ids.append(m.id)
            member.last_read_message_id = up_to_message_id
        self.commit()
        if read_ids:
            sender_ids = set()
            for mid in read_ids:
                msg = self.messages.get(mid)
                if msg:
                    sender_ids.add(msg.sender_id)
            await self.ws.send_to_users(
                list(sender_ids),
                Envelope(type=EventType.MESSAGE_READ, conversation_id=conversation_id,
                         data={"message_ids": read_ids, "user_id": user_id}),
            )

    # ------------------------------------------------------------------ #
    # Reactions
    # ------------------------------------------------------------------ #

    async def react(self, actor_id: str, message_id: str, emoji: str, reaction_type: str) -> None:
        message = self.messages.get(message_id)
        if message is None:
            raise NotFoundError("Message not found.")
        self._require_active_member(actor_id, message.conversation_id)
        existing = self.reactions.by_user(message_id, actor_id, emoji)
        if existing is None:
            self.reactions.add(
                MessageReaction(
                    message_id=message_id, user_id=actor_id, emoji=emoji, reaction_type=reaction_type or "custom"
                )
            )
            self.commit()
            await self.ws.broadcast_to_conversation(
                message.conversation_id,
                Envelope(type=EventType.REACTION_CREATED, conversation_id=message.conversation_id,
                         data={"message_id": message_id, "user_id": actor_id, "emoji": emoji}),
            )

    async def unreact(self, actor_id: str, message_id: str, emoji: str) -> None:
        message = self.messages.get(message_id)
        if message is None:
            raise NotFoundError("Message not found.")
        existing = self.reactions.by_user(message_id, actor_id, emoji)
        if existing is not None:
            self.reactions.delete(existing)
            self.commit()
            await self.ws.broadcast_to_conversation(
                message.conversation_id,
                Envelope(type=EventType.REACTION_REMOVED, conversation_id=message.conversation_id,
                         data={"message_id": message_id, "user_id": actor_id, "emoji": emoji}),
            )

    # ------------------------------------------------------------------ #
    # Edits / deletes
    # ------------------------------------------------------------------ #

    async def edit(self, actor_id: str, message_id: str, payload: EditMessagePayload) -> MessageOut:
        message = self._owned_message(actor_id, message_id)
        from app.models.message import MessageEdit

        self.edits.add(
            MessageEdit(message_id=message.id, editor_id=actor_id, previous_body=message.body or "")
        )
        message.body = payload.body
        message.is_edited = True
        self.commit()
        out = self._to_out(message)
        await self.ws.broadcast_to_conversation(
            message.conversation_id,
            Envelope(type=EventType.MESSAGE_UPDATED, conversation_id=message.conversation_id, data={"message": out.model_dump()}),
        )
        return out

    async def delete(self, actor_id: str, message_id: str, delete_for: str) -> None:
        message = self.messages.get(message_id)
        if message is None:
            raise NotFoundError("Message not found.")
        self._require_active_member(actor_id, message.conversation_id)
        if delete_for not in ("me", "everyone"):
            raise ValidationAppError("delete_for must be 'me' or 'everyone'.", code="bad_delete_for")
        if delete_for == "everyone" and message.sender_id != actor_id:
            if self.members.role_of(message.conversation_id, actor_id).value == "member":
                raise ForbiddenError("Only the sender (or an admin) can delete for everyone.")
        self.deletions.add(self.deletions.model(message_id=message.id, deleted_by=actor_id, delete_for=delete_for))
        deleted_content = None
        if delete_for == "everyone":
            deleted_content = message.body
            message.body = None
            for att in message.attachments:
                self.attachments.delete(att)
        elif message.sender_id != actor_id:
            # "delete for me" of a peer message: record a local receipt tombstone.
            self.receipts.mark_delivered(message.id, actor_id, message.conversation_id)
            self.commit()
            return

        self.commit()
        await self.ws.broadcast_to_conversation(
            message.conversation_id,
            Envelope(type=EventType.MESSAGE_DELETED, conversation_id=message.conversation_id,
                     data={"message_id": message.id, "delete_for": delete_for, "deleted_content": deleted_content}),
        )

    # ------------------------------------------------------------------ #
    # Forwarding / copying reference
    # ------------------------------------------------------------------ #

    async def forward(self, actor_id: str, message_id: str, to_conversation_ids: list[str]) -> list[MessageOut]:
        source = self.messages.get(message_id)
        if source is None:
            raise NotFoundError("Message not found.")
        self._require_active_member(actor_id, source.conversation_id)
        created: list[MessageOut] = []
        for cid in to_conversation_ids:
            if cid == source.conversation_id:
                self._require_active_member(actor_id, cid)
                result = await self.send(actor_id, SendMessagePayload(conversation_id=cid, kind=source.kind, body=source.body, metadata={"forwarded": source.id}))
                created.append(result.message)
            else:
                if self.conversations.get(cid) is None:
                    raise NotFoundError("One or more conversations not found.")
                self._require_active_member(actor_id, cid)
                result = await self.send(actor_id, SendMessagePayload(conversation_id=cid, kind=source.kind, body=source.body, metadata={"forwarded": source.id}))
                created.append(result.message)
        return created

    # ------------------------------------------------------------------ #
    # Reading / searching
    # ------------------------------------------------------------------ #

    def list_before(self, user_id: str, conversation_id: str, before_server_id: Optional[int], limit: int = 30) -> MessageList:
        self._require_active_member(user_id, conversation_id)
        if before_server_id is None:
            rows = self.messages.by_server_range(conversation_id, limit=limit)
            items = [self._to_out(m) for m in rows]
            has_more = len(items) == limit
            next_cursor = str(rows[-1].server_id - 1) if items else None
            return MessageList(items=items, has_more=has_more, next_cursor=next_cursor)
        rows = self.messages.before(conversation_id, before_server_id, limit=limit)
        items = [self._to_out(m) for m in rows]
        return MessageList(items=items, has_more=len(items) == limit, next_cursor=str(rows[-1].server_id - 1) if items else None)

    def search(self, user_id: str, query: str, conversation_id: Optional[str], limit: int = 30) -> MessageList:
        conv_ids = None
        if conversation_id:
            self._require_active_member(user_id, conversation_id)
            conv_ids = [conversation_id]
        else:
            conv_ids = self.members.member_ids_of_all(user_id)
        if not conv_ids:
            return MessageList(items=[])
        rows = self.messages.global_search(user_id, conv_ids, query, limit=limit)
        return MessageList(items=[self._to_out(m) for m in rows], has_more=len(rows) == limit)

    # ------------------------------------------------------------------ #
    # Typing indicators
    # ------------------------------------------------------------------ #

    async def typing_started(self, user_id: str, conversation_id: str) -> None:
        self._require_active_member(user_id, conversation_id)
        await self.ws.set_typing(user_id, conversation_id)
        await self.ws.broadcast_to_conversation(
            conversation_id,
            Envelope(type=EventType.TYPING_STARTED, conversation_id=conversation_id, data={"user_id": user_id}),
        )

    async def typing_stopped(self, user_id: str, conversation_id: str) -> None:
        await self.ws.clear_typing(user_id, conversation_id)
        await self.ws.broadcast_to_conversation(
            conversation_id,
            Envelope(type=EventType.TYPING_STOPPED, conversation_id=conversation_id, data={"user_id": user_id}),
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    async def _evaluate_streak(self, actor_id: str, conversation_id: str, at: datetime) -> None:
        streak_engine = StreakEngine(db=self.db, ws=self.ws)
        await streak_engine.record_activity(
            actor_id=actor_id, peer_user_id=self._peer_of_direct(conversation_id, actor_id),
            conversation_id=conversation_id, sent_at=at,
        )

    def _peer_of_direct(self, conversation_id: str, actor_id: str) -> str:
        members = self.members.member_ids(conversation_id)
        return next((m for m in members if m != actor_id), "")

    def _require_active_member(self, user_id: str, conversation_id: str):
        member = self.members.member(conversation_id, user_id)
        if member is None or member.left_at is not None:
            raise ForbiddenError("You are not part of this conversation.")
        return member

    def _owned_message(self, actor_id: str, message_id: str) -> Message:
        message = self.messages.get(message_id)
        if message is None or message.sender_id != actor_id:
            raise ForbiddenError("You can only edit your own messages.")
        return message

    def _to_out(self, message: Message) -> MessageOut:
        attachments = list(message.attachments)
        reactions = self.reactions.for_message(message.id)
        status = MessageServerStatus.SENT
        read_receipt = self.receipts.for_message(message.id)
        delivery: dict[str, str] = {}
        for r in read_receipt:
            if r.read_at is not None:
                delivery[r.user_id] = "read"
            elif r.received_at is not None:
                delivery[r.user_id] = "delivered"
        return MessageOut(
            id=message.id,
            server_id=message.server_id,
            conversation_id=message.conversation_id,
            sender_id=message.sender_id,
            kind=message.kind,
            body=message.body,
            client_id=message.client_id,
            reply_to_message_id=message.reply_to_message_id,
            attachments=[self._attach_out(a) for a in attachments],
            reactions=[self._reaction_out(r) for r in reactions],
            sent_at=message.sent_at,
            status=status,
            delivery_statuses=delivery,
            is_edited=message.is_edited,
        )

    @staticmethod
    def _attach_out(a: MessageAttachment):
        from app.schemas.media import AttachmentOut

        return AttachmentOut(
            id=a.id, kind=a.kind, url=a.url, thumb_url=a.thumb_url, mime_type=a.mime_type,
            size_bytes=a.size_bytes, duration_ms=a.duration_ms, width=a.width, height=a.height,
            file_name=a.file_name, waveform=a.waveform,
        )

    @staticmethod
    def _reaction_out(r: MessageReaction):
        from app.schemas.message import ReactionOut

        return ReactionOut(id=r.id, user_id=r.user_id, emoji=r.emoji, reaction_type=r.reaction_type, created_at=r.created_at)