"""Conversation service: direct/group lifecycle, membership, permissions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import (
    MAX_GROUP_MEMBERS,
    ConversationType,
    MemberRole,
    MessageKind,
)
from app.core.events import Envelope, EventType
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models.conversation import Conversation, ConversationMember
from app.models.message import Message
from app.repositories.conversation_repo import ConversationMemberRepository, ConversationRepository
from app.repositories.user_repo import BlockRepository, UserRepository
from app.schemas.conversation import (
    AddMembersPayload,
    ConversationDetail,
    ConversationList,
    ConversationMemberPublic,
    ConversationSummary,
    CreateGroupPayload,
    UpdateGroupPayload,
)
from app.services.base import Service
from app.services.user_service import to_public


class ConversationService(Service):
    def __init__(self, db: Session, **kwargs):
        super().__init__(db, **kwargs)
        self.conversations = ConversationRepository(db)
        self.members = ConversationMemberRepository(db)
        self.users = UserRepository(db)
        self.blocks = BlockRepository(db)

    # ------------------------------------------------------------------ #
    # Creation
    # ------------------------------------------------------------------ #

    async def create_direct(self, actor_id: str, peer_id: str) -> ConversationDetail:
        if actor_id == peer_id:
            raise ForbiddenError("You cannot message yourself.")
        if self.blocks.is_blocked(actor_id, peer_id) or self.blocks.is_blocked(peer_id, actor_id):
            raise NotFoundError("User not found.")
        peer = self.users.get(peer_id)
        if peer is None:
            raise NotFoundError("User not found.")

        existing = self.conversations.direct_between(actor_id, peer_id)
        if existing:
            self._restore_membership(existing.id, actor_id, peer_id)
            detail = self.get_detail(actor_id, existing.id)
            return detail

        conv = Conversation(
            type=ConversationType.DIRECT,
            direct_key=self.conversations.direct_key(actor_id, peer_id),
        )
        self.conversations.add(conv)
        self.flush()
        now = datetime.now(timezone.utc)
        self.members.add(ConversationMember(conversation_id=conv.id, user_id=actor_id, role=MemberRole.OWNER, joined_at=now))
        self.members.add(ConversationMember(conversation_id=conv.id, user_id=peer_id, role=MemberRole.MEMBER, joined_at=now))
        self.commit()
        detail = self.get_detail(actor_id, conv.id)
        self.ws.join_room(peer_id, conv.id)
        await self.ws.send_to_user(
            peer_id, Envelope(type=EventType.CONVERSATION_UPDATED, conversation_id=conv.id, data={"created": True})
        )
        return detail

    async def create_group(self, actor_id: str, payload: CreateGroupPayload) -> ConversationDetail:
        member_ids = list(dict.fromkeys([actor_id, *payload.member_ids]))
        if len(member_ids) > MAX_GROUP_MEMBERS:
            raise ConflictError(f"Groups are limited to {MAX_GROUP_MEMBERS} members.", code="group_too_large")
        other_ids = [i for i in member_ids if i != actor_id]
        users = {u.id: u for u in self.users.by_ids(other_ids)}
        for uid in other_ids:
            if uid not in users:
                raise NotFoundError("One of the added users does not exist.")

        conv = Conversation(
            type=ConversationType.GROUP,
            name=payload.name,
            description=payload.description,
        )
        self.conversations.add(conv)
        self.flush()
        now = datetime.now(timezone.utc)
        self.members.add(ConversationMember(conversation_id=conv.id, user_id=actor_id, role=MemberRole.OWNER, joined_at=now))
        admin_set = set(payload.admin_ids)
        for uid in member_ids[1:]:
            role = MemberRole.ADMIN if uid in admin_set else MemberRole.MEMBER
            self.members.add(ConversationMember(conversation_id=conv.id, user_id=uid, role=role, joined_at=now))
        self.db.flush()
        self._insert_system_message(conv.id, actor_id, f"{actor_id} created the group “{payload.name}”", now)
        self.commit()
        detail = self.get_detail(actor_id, conv.id)
        for uid in member_ids:
            self.ws.join_room(uid, conv.id)
        return detail

    # ------------------------------------------------------------------ #
    # Reading / listing
    # ------------------------------------------------------------------ #

    def list_for_user(self, user_id: str, limit: int = 30) -> ConversationList:
        rows = self.conversations.list_for_user(user_id, limit=limit)
        summaries = [self._summarize(conv, user_id) for conv in rows]
        return ConversationList(items=summaries, has_more=len(rows) == limit)

    def get_detail(self, user_id: str, conversation_id: str) -> ConversationDetail:
        conv = self._require_member(user_id, conversation_id)
        members = self.members.members_of(conversation_id)
        user_ids = [m.user_id for m in members]
        users = {u.id: u for u in self.users.by_ids(user_ids)}
        online = {i for i in user_ids if self.ws.is_online(i)}

        member_out = [
            ConversationMemberPublic(
                user=to_public(users[m.user_id], online_ids=online),
                role=m.role,
                joined_at=m.joined_at,
                is_muted=m.is_muted,
            )
            for m in members
            if m.user_id in users
        ]
        me = self.members.member(conversation_id, user_id)
        summary = self._summarize(conv, user_id)
        detail = ConversationDetail(
            **summary.model_dump(),
            members=member_out,
            role=me.role if me else MemberRole.MEMBER,
            members_can_add=conv.members_can_add,
            members_can_edit_group_info=conv.members_can_edit_group_info,
            admin_only_messaging=conv.admin_only_messaging,
        )
        return detail

    # ------------------------------------------------------------------ #
    # Group management
    # ------------------------------------------------------------------ #

    async def update_group(self, actor_id: str, conversation_id: str, payload: UpdateGroupPayload) -> ConversationDetail:
        conv = self._require_member(actor_id, conversation_id)
        self._require_admin_or(conv, actor_id, allow_edit_group_info=conv.members_can_edit_group_info)
        if payload.name is not None:
            conv.name = payload.name
        if payload.description is not None:
            conv.description = payload.description
        if payload.photo_url is not None:
            conv.photo_url = payload.photo_url
        if payload.members_can_add is not None:
            conv.members_can_add = payload.members_can_add
        if payload.members_can_edit_group_info is not None:
            conv.members_can_edit_group_info = payload.members_can_edit_group_info
        if payload.admin_only_messaging is not None:
            conv.admin_only_messaging = payload.admin_only_messaging
        self.db.flush()
        self._insert_system_message(conversation_id, actor_id, f"{actor_id} updated the group", datetime.now(timezone.utc))
        self.commit()
        await self._notify_members(conversation_id, Envelope(type=EventType.CONVERSATION_UPDATED, conversation_id=conversation_id, data={"updated": True}))
        return self.get_detail(actor_id, conversation_id)

    async def add_members(self, actor_id: str, conversation_id: str, payload: AddMembersPayload) -> ConversationDetail:
        conv = self._require_member(actor_id, conversation_id)
        self._require_admin_or(conv, actor_id, allow_add=conv.members_can_add)
        current = set(self.members.member_ids(conversation_id))
        to_add = [i for i in dict.fromkeys(payload.user_ids) if i not in current]
        if len(current) + len(to_add) > conv.max_members:
            raise ConflictError("Adding these members would exceed the group limit.", code="group_full")
        targets = {u.id: u for u in self.users.by_ids(to_add)}
        for uid in to_add:
            if uid not in targets:
                raise NotFoundError("One of the added users does not exist.")
            role = MemberRole.ADMIN if (payload.as_admins and self.members.role_of(conversation_id, actor_id) in (MemberRole.OWNER, MemberRole.ADMIN)) else MemberRole.MEMBER
            self.members.add(ConversationMember(conversation_id=conversation_id, user_id=uid, role=role))
            self.ws.join_room(uid, conversation_id)
        self.db.flush()
        self._insert_system_message(conversation_id, actor_id, f"{actor_id} added {len(to_add)} member(s)", datetime.now(timezone.utc))
        self.commit()
        await self._notify_members(conversation_id, Envelope(type=EventType.CONVERSATION_MEMBERSHIP_CHANGED, conversation_id=conversation_id, data={"added": to_add}))
        return self.get_detail(actor_id, conversation_id)

    async def remove_member(self, actor_id: str, conversation_id: str, target_id: str) -> None:
        conv = self._require_member(actor_id, conversation_id)
        actor_role = self.members.role_of(conversation_id, actor_id)
        target_role = self.members.role_of(conversation_id, target_id)
        if target_role is None:
            raise NotFoundError("That user is not a member.")
        if actor_role == MemberRole.MEMBER:
            raise ForbiddenError("Only admins can remove members.")
        if actor_role == MemberRole.ADMIN and target_role in (MemberRole.ADMIN, MemberRole.OWNER):
            raise ForbiddenError("Admins cannot remove other admins or the owner.")
        self.members.mark_left(conversation_id, target_id)
        self.db.flush()
        self._insert_system_message(conversation_id, actor_id, f"{actor_id} removed a member", datetime.now(timezone.utc))
        self.commit()
        self.ws.leave_room(target_id, conversation_id)

    async def leave_group(self, actor_id: str, conversation_id: str) -> None:
        conv = self._require_member(actor_id, conversation_id)
        if conv.type == ConversationType.DIRECT:
            raise ForbiddenError("You cannot leave a direct conversation.")
        self.members.mark_left(conversation_id, actor_id)
        self.db.flush()
        now = datetime.now(timezone.utc)
        self._insert_system_message(conversation_id, actor_id, f"{actor_id} left the group", now)
        owners = [
            m.user_id
            for m in self.members.members_of(conversation_id)
            if m.role == MemberRole.OWNER
        ]
        remaining = [m.user_id for m in self.members.members_of(conversation_id)]
        if actor_id in owners and remaining:
            # Transfer ownership to the longest-standing admin/member.
            new_owner = self.members.member(conversation_id, remaining[0])
            if new_owner:
                new_owner.role = MemberRole.OWNER
        self.commit()
        self.ws.leave_room(actor_id, conversation_id)
        await self._notify_members(conversation_id, Envelope(type=EventType.CONVERSATION_MEMBERSHIP_CHANGED, conversation_id=conversation_id, data={"left": actor_id}))

    async def promote(self, actor_id: str, conversation_id: str, target_id: str) -> None:
        self._require_owner(actor_id, conversation_id)
        member = self._target_member(conversation_id, target_id)
        member.role = MemberRole.ADMIN
        self.commit()
        await self._notify_members(conversation_id, Envelope(type=EventType.CONVERSATION_UPDATED, conversation_id=conversation_id, data={"role_changed": target_id}))

    async def demote(self, actor_id: str, conversation_id: str, target_id: str) -> None:
        self._require_owner(actor_id, conversation_id)
        member = self._target_member(conversation_id, target_id)
        member.role = MemberRole.MEMBER
        self.commit()
        await self._notify_members(conversation_id, Envelope(type=EventType.CONVERSATION_UPDATED, conversation_id=conversation_id, data={"role_changed": target_id}))

    async def set_muted(self, user_id: str, conversation_id: str, muted: bool) -> None:
        member = self._require_member_model(user_id, conversation_id)
        member.is_muted = muted
        self.commit()

    async def set_pinned(self, user_id: str, conversation_id: str, pinned: bool) -> None:
        member = self._require_member_model(user_id, conversation_id)
        member.pinned = pinned
        self.commit()

    async def hide_conversation(self, user_id: str, conversation_id: str) -> None:
        member = self._require_member_model(user_id, conversation_id)
        member.is_visible = False
        self.commit()

    async def mark_read(self, user_id: str, conversation_id: str, up_to_message_id: Optional[str] = None) -> None:
        member = self._require_member_model(user_id, conversation_id)
        self.members.reset_unread(conversation_id, user_id)
        if up_to_message_id:
            member.last_read_message_id = up_to_message_id
        self.commit()
        await self.ws.send_to_user(
            user_id,
            Envelope(type=EventType.UNREAD_COUNT_UPDATED, conversation_id=conversation_id, data={"unread_count": 0}),
        )

    # ------------------------------------------------------------------ #
    # Summaries / helpers
    # ------------------------------------------------------------------ #

    def _summarize(self, conv: Conversation, viewer_id: str) -> ConversationSummary:
        last_message = self.db.scalar(
            select(Message).where(Message.conversation_id == conv.id).order_by(Message.server_id.desc()).limit(1)
        )
        member_row = self.members.member(conv.id, viewer_id)
        peer_public = None
        peer = None
        if conv.type == ConversationType.DIRECT:
            members = self.members.member_ids(conv.id)
            peer_id = next((i for i in members if i != viewer_id), None)
            if peer_id:
                other = self.users.get(peer_id)
                if other:
                    peer_public = to_public(
                        other,
                        online_ids={peer_id} if self.ws.is_online(peer_id) else set(),
                    )
                    peer = peer_public

        return ConversationSummary(
            id=conv.id,
            type=conv.type,
            name=conv.name if conv.type == ConversationType.GROUP else None,
            photo_url=conv.photo_url,
            last_message_preview=last_message.body if last_message else None,
            last_message_at=conv.last_message_at,
            last_message_sender_id=last_message.sender_id if last_message else None,
            unread_count=member_row.unread_count if member_row else 0,
            is_pinned=member_row.pinned if member_row else False,
            is_muted=member_row.is_muted if member_row else False,
            member_count=self.members.count_members(conv.id),
            peer=peer,
        )

    def _require_member_model(self, user_id: str, conversation_id: str) -> ConversationMember:
        member = self.members.member(conversation_id, user_id)
        if member is None or member.left_at is not None:
            raise ForbiddenError("You are not part of this conversation.")
        return member

    def _require_member(self, user_id: str, conversation_id: str) -> Conversation:
        self._require_member_model(user_id, conversation_id)
        conv = self.conversations.get(conversation_id)
        if conv is None:
            raise NotFoundError("Conversation not found.")
        return conv

    def _require_owner(self, actor_id: str, conversation_id: str) -> None:
        role = self.members.role_of(conversation_id, actor_id)
        if role != MemberRole.OWNER:
            raise ForbiddenError("Only the group owner can do that.")

    def _require_admin_or(self, conv: Conversation, actor_id: str, *, allow_add=False, allow_edit_group_info=False) -> None:
        role = self.members.role_of(conv.id, actor_id)
        if role == MemberRole.OWNER:
            return
        if role == MemberRole.ADMIN:
            return
        if role == MemberRole.MEMBER and allow_add and conv.members_can_add:
            return
        if role == MemberRole.MEMBER and allow_edit_group_info and conv.members_can_edit_group_info:
            return
        raise ForbiddenError("You do not have permission to do that.")

    def _target_member(self, conversation_id: str, target_id: str) -> ConversationMember:
        member = self.members.member(conversation_id, target_id)
        if member is None:
            raise NotFoundError("That user is not a member.")
        return member

    def _insert_system_message(self, conversation_id: str, sender_id: str, body: str, now: datetime) -> None:
        repo = self.conversations
        conv = repo.get(conversation_id)
        next_id = 0
        existing_max = self.db.scalar(select(Message.server_id).where(Message.conversation_id == conversation_id).order_by(Message.server_id.desc()).limit(1))
        next_id = (int(existing_max) if existing_max else 0) + 1
        msg = Message(
            conversation_id=conversation_id,
            sender_id=sender_id,
            kind=MessageKind.SYSTEM,
            body=body,
            server_id=next_id,
            sent_at=now,
            is_system=True,
        )
        self.db.add(msg)
        if conv:
            conv.last_message_at = now

    def _restore_membership(self, conversation_id: str, a: str, b: str) -> None:
        for uid in (a, b):
            member = self.members.member(conversation_id, uid)
            if member:
                member.left_at = None
                member.is_visible = True

    async def _notify_members(self, conversation_id: str, envelope: Envelope) -> None:
        await self.ws.broadcast_to_conversation(conversation_id, envelope)