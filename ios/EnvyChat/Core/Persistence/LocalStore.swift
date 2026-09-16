import Foundation
import SwiftData

/// Local first-class citizen cache: conversations, messages, and a send outbox.
@Model
final class ConversationCache {
    @Attribute(.unique) var id: String
    var name: String?
    var peerID: String?
    var lastMessagePreview: String?
    var lastMessageAt: Date?
    var unreadCount: Int

    init(id: String, name: String?, peerID: String?, lastMessagePreview: String?, lastMessageAt: Date?, unreadCount: Int) {
        self.id = id
        self.name = name
        self.peerID = peerID
        self.lastMessagePreview = lastMessagePreview
        self.lastMessageAt = lastMessageAt
        self.unreadCount = unreadCount
    }
}

@Model
final class MessageCache {
    @Attribute(.unique) var id: String
    var conversationID: String
    var senderID: String
    var body: String?
    var clientID: String?
    var sentAt: Date
    var isEdited: Bool
    var status: String

    init(id: String, conversationID: String, senderID: String, body: String?, clientID: String?, sentAt: Date, isEdited: Bool, status: String) {
        self.id = id
        self.conversationID = conversationID
        self.senderID = senderID
        self.body = body
        self.clientID = clientID
        self.sentAt = sentAt
        self.isEdited = isEdited
        self.status = status
    }
}

@Model
final class OutboxEntry {
    @Attribute(.unique) var clientID: String
    var conversationID: String
    var body: String
    var createdAt: Date
    var status: String

    init(clientID: String, conversationID: String, body: String, createdAt: Date, status: String = "queued") {
        self.clientID = clientID
        self.conversationID = conversationID
        self.body = body
        self.createdAt = createdAt
        self.status = status
    }
}

/// Wraps SwiftData fetching/upserting for the offline-first store.
@MainActor
@Observable
final class LocalStore {
    let container: ModelContainer
    let context: ModelContext

    init() {
        let schema = Schema([ConversationCache.self, MessageCache.self, OutboxEntry.self])
        container = try! ModelContainer(for: schema)
        context = container.mainContext
    }

    func upsert(_ conversation: ConversationSummary) {
        let id = conversation.id
        let cache = (try? context.fetch(FetchDescriptor<ConversationCache>(predicate: #Predicate { $0.id == id })).first)
            ?? ConversationCache(id: conversation.id, name: nil, peerID: nil, lastMessagePreview: nil, lastMessageAt: nil, unreadCount: 0)
        cache.name = conversation.name
        cache.peerID = conversation.peer?.id
        cache.lastMessagePreview = conversation.lastMessagePreview
        cache.lastMessageAt = conversation.lastMessageAt
        cache.unreadCount = conversation.unreadCount
        try? context.save()
    }

    func upsert(_ message: MessageOut) {
        let id = message.id
        let cache = (try? context.fetch(FetchDescriptor<MessageCache>(predicate: #Predicate { $0.id == id })).first)
            ?? MessageCache(id: message.id, conversationID: message.conversationId, senderID: message.senderId, body: nil, clientID: nil, sentAt: .distantPast, isEdited: false, status: "")
        cache.body = message.body
        cache.clientID = message.clientId
        cache.sentAt = message.sentAt
        cache.isEdited = message.isEdited
        cache.status = message.status
        try? context.save()
    }

    func queuedMessages(in conversationID: String) -> [MessageCache] {
        let descriptor = FetchDescriptor<MessageCache>(
            predicate: #Predicate { $0.conversationID == conversationID },
            sortBy: [SortDescriptor(\.sentAt)]
        )
        return (try? context.fetch(descriptor)) ?? []
    }

    func enqueue(conversationID: String, body: String) -> String {
        let clientID = UUID().uuidString.lowercased()
        context.insert(
            OutboxEntry(clientID: clientID, conversationID: conversationID, body: body, createdAt: Date())
        )
        try? context.save()
        return clientID
    }

    func pendingOutbox() -> [OutboxEntry] {
        let descriptor = FetchDescriptor<OutboxEntry>(predicate: #Predicate { $0.status == "queued" })
        return (try? context.fetch(descriptor)) ?? []
    }

    func flush(_ entry: OutboxEntry) {
        context.delete(entry)
        try? context.save()
    }
}