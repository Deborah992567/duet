"""SQLAlchemy model exports (import this module to register all tables)."""

from app.models.call import Call, CallParticipant
from app.models.conversation import Conversation, ConversationMember
from app.models.friendship import FriendRequest, Friendship
from app.models.message import (
    Message,
    MessageAttachment,
    MessageDeletion,
    MessageEdit,
    MessageReaction,
    MessageReceipt,
)
from app.models.notification import Notification, NotificationPreference
from app.models.report import Report
from app.models.streak import Streak, StreakDayQualification, StreakEvent
from app.models.user import BlockedUser, Device, User, UserProfile

# Ensure all models are discoverable by Alembic autogenerate.
__all__ = [
    "BlockedUser",
    "Call",
    "CallParticipant",
    "Conversation",
    "ConversationMember",
    "Device",
    "FriendRequest",
    "Friendship",
    "Message",
    "MessageAttachment",
    "MessageDeletion",
    "MessageEdit",
    "MessageReaction",
    "MessageReceipt",
    "Notification",
    "NotificationPreference",
    "Report",
    "Streak",
    "StreakDayQualification",
    "StreakEvent",
    "User",
    "UserProfile",
]