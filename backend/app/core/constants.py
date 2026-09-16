"""Shared domain enums and constants used across services and schemas."""

from __future__ import annotations

import enum


class StrEnum(str, enum.Enum):
    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class UserStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class FriendshipStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    REMOVED = "removed"
    BLOCKED = "blocked"


class ConversationType(StrEnum):
    DIRECT = "direct"
    GROUP = "group"


class MemberRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class MessageKind(StrEnum):
    TEXT = "text"
    EMOJI = "emoji"
    STICKER = "sticker"
    GIF = "gif"
    IMAGE = "image"
    VIDEO = "video"
    FILE = "file"
    VOICE = "voice"
    CONTACT = "contact"
    LOCATION = "location"
    SYSTEM = "system"


class MessageClientStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageServerStatus(StrEnum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"


class ReactionType(StrEnum):
    LIKE = "like"
    LOVE = "love"
    LAUGH = "laugh"
    WOW = "wow"
    SAD = "sad"
    ANGRY = "angry"
    CUSTOM = "custom"


class CallKind(StrEnum):
    VOICE = "voice"
    VIDEO = "video"


class CallDirection(StrEnum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class CallState(StrEnum):
    RINGING = "ringing"
    CONNECTING = "connecting"
    ACTIVE = "active"
    ENDED = "ended"
    MISSED = "missed"
    REJECTED = "rejected"
    CANCELED = "canceled"


class NotificationKind(StrEnum):
    MESSAGE = "message"
    GROUP_MESSAGE = "group_message"
    FRIEND_REQUEST = "friend_request"
    FRIEND_ACCEPTED = "friend_accepted"
    CALL = "call"
    STREAK = "streak"
    STREAK_MILESTONE = "streak_milestone"
    STREAK_REMINDER = "streak_reminder"
    SECURITY = "security"
    SYSTEM = "system"


class ReportStatus(StrEnum):
    OPEN = "open"
    REVIEWING = "reviewing"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class ReportKind(StrEnum):
    USER = "user"
    MESSAGE = "message"
    CONVERSATION = "conversation"


class MediaKind(StrEnum):
    IMAGE = "image"
    VIDEO = "video"
    FILE = "file"
    VOICE = "voice"
    STICKER = "sticker"
    GIF = "gif"
    AVATAR = "avatar"


class DevicePlatform(StrEnum):
    IOS = "ios"


class PresenceStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    AWAY = "away"


# Range limits / validation
MAX_PROFILE_IMAGE_BYTES = 8 * 1024 * 1024
MAX_GROUP_MEMBERS = 512
MAX_MESSAGE_ATTACHMENTS = 4
MAX_MESSAGE_LENGTH = 4000
MAX_DISPLAY_NAME_LENGTH = 32
MAX_USERNAME_LENGTH = 20
MAX_BIO_LENGTH = 160
MAX_GROUP_NAME_LENGTH = 60

DEFAULT_UNREAD_THRESHOLD_DAYS = 90