import Foundation

struct ConversationSummary: Decodable, Identifiable, Hashable {
    let id: String
    let type: String
    let name: String?
    let lastMessagePreview: String?
    let lastMessageAt: Date?
    let unreadCount: Int
    let isPinned: Bool
    let isMuted: Bool
    let memberCount: Int
    let peer: UserPublic?
    let currentStreak: Int
    let streakAlive: Bool

    enum CodingKeys: String, CodingKey {
        case id, type, name, peer
        case lastMessagePreview = "last_message_preview"
        case lastMessageAt = "last_message_at"
        case unreadCount = "unread_count"
        case isPinned = "is_pinned"
        case isMuted = "is_muted"
        case memberCount = "member_count"
        case currentStreak = "current_streak"
        case streakAlive = "streak_alive"
    }
}

struct ConversationListResponse: Decodable {
    let items: [ConversationSummary]
    let hasMore: Bool

    enum CodingKeys: String, CodingKey {
        case items
        case hasMore = "has_more"
    }
}

struct MessageOut: Decodable, Identifiable, Hashable {
    let id: String
    let conversationId: String
    let senderId: String
    let body: String?
    let clientId: String?
    let sentAt: Date
    let isEdited: Bool
    let status: String

    enum CodingKeys: String, CodingKey {
        case id, body, status
        case conversationId = "conversation_id"
        case senderId = "sender_id"
        case clientId = "client_id"
        case sentAt = "sent_at"
        case isEdited = "is_edited"
    }
}

struct MessageListResponse: Decodable {
    let items: [MessageOut]
    let hasMore: Bool

    enum CodingKeys: String, CodingKey {
        case items
        case hasMore = "has_more"
    }
}

struct SendMessageResult: Decodable {
    let message: MessageOut
    let clientId: String?

    enum CodingKeys: String, CodingKey {
        case message
        case clientId = "client_id"
    }
}