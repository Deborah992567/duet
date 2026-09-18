import Foundation
import Observation

struct MediaSendBody: Encodable {
    let kind: String
    let client_id: String
    let attachments: [AttachmentDraftBody]
}

struct SendTextBody: Encodable {
    let body: String
    let client_id: String
    let reply_to_message_id: String?
}

struct AttachmentDraftBody: Encodable {
    let upload_id: String
    let kind: String
    let file_name: String
    let duration_ms: Int
}

@MainActor
@Observable
final class ChatMessageStore {
    private(set) var messages: [MessageOut] = []
    private(set) var isLoading = false
    var errorText: String?

    let conversationID: String
    private let client = APIClient.shared
    private var local: LocalStore?

    init(conversationID: String, local: LocalStore?) {
        self.conversationID = conversationID
        self.local = local
    }

    func bind(_ cache: LocalStore) {
        local = cache
    }

    func hydrate(from cache: [MessageCache]) {
        let cached = cache.map {
            MessageOut(
                id: $0.id, conversationId: $0.conversationID, senderId: $0.senderID,
                body: $0.body, clientId: $0.clientID, sentAt: $0.sentAt,
                isEdited: $0.isEdited, status: $0.status, attachments: []
            )
        }
        let merged = Dictionary(uniqueKeysWithValues: (messages + cached).map { ($0.id, $0) }).values.sorted { $0.sentAt < $1.sentAt }
        messages = Array(merged)
    }

    func loadHistory() async {
        isLoading = true
        defer { isLoading = false }
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversationID)/messages")
        do {
            let resp: MessageListResponse = try await client.send(builder, as: MessageListResponse.self)
            messages = resp.items.sorted { $0.sentAt < $1.sentAt }
        } catch {
            errorText = (error as? APIError)?.message ?? "Could not load messages."
        }
    }

    func send(body: String, clientID: String, replyTo: String? = nil) async -> Bool {
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/conversations/\(conversationID)/messages",
            method: .post,
            body: SendTextBody(body: body, client_id: clientID, reply_to_message_id: replyTo)
        )
        do {
            let result: SendMessageResult = try await client.send(builder, as: SendMessageResult.self)
            if let index = messages.firstIndex(where: { $0.clientId == clientID }) {
                messages[index] = result.message
            } else {
                messages.append(result.message)
            }
            local?.upsert(result.message)
            try? await markRead(upTo: result.message.id)
            return true
        } catch {
            if let cache = local {
                let outgoing = MessageOut(
                    id: "pending-\(clientID)", conversationId: conversationID,
                    senderId: SessionStore.shared.currentUserID ?? "me",
                    body: body, clientId: clientID, sentAt: Date(), isEdited: false, status: "pending",
                    attachments: []
                )
                var next = messages
                next.append(outgoing)
                next.sort { $0.sentAt < $1.sentAt }
                messages = next
                _ = cache
            }
            return false
        }
    }

    func markRead(upTo messageID: String) async throws {
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/conversations/\(conversationID)/read",
            method: .post,
            body: ["up_to_message_id": messageID]
        )
        _ = try await client.send(builder, as: NoContent.self, defaultValue: NoContent())
    }

    func sendVoiceIfNeeded(recordedAt url: URL, durationMs: Int, uploader: MediaUploader) async {
        guard let uploadID = await uploader.uploadVoice(url: url) else {
            errorText = "Voice upload failed."
            return
        }
        let clientID = UUID().uuidString.lowercased()
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/conversations/\(conversationID)/messages",
            method: .post,
            body: MediaSendBody(kind: "voice", client_id: clientID, attachments: [AttachmentDraftBody(upload_id: uploadID, kind: "voice", file_name: "talk.m4a", duration_ms: durationMs)])
        )
        do {
            let result: SendMessageResult = try await client.send(builder, as: SendMessageResult.self)
            if let index = messages.firstIndex(where: { $0.clientId == clientID }) {
                messages[index] = result.message
            } else {
                messages.append(result.message)
            }
            local?.upsert(result.message)
            try? await markRead(upTo: result.message.id)
        } catch {
            errorText = (error as? APIError)?.message ?? "Voice message failed."
        }
    }

    func sendImageIfNeeded(url: URL, uploader: MediaUploader) async {
        guard let uploadID = await uploader.uploadImage(url: url) else {
            errorText = "Image upload failed."
            return
        }
        let clientID = UUID().uuidString.lowercased()
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/conversations/\(conversationID)/messages",
            method: .post,
            body: MediaSendBody(kind: "image", client_id: clientID, attachments: [AttachmentDraftBody(upload_id: uploadID, kind: "image", file_name: "image.jpg", duration_ms: 0)])
        )
        do {
            let result: SendMessageResult = try await client.send(builder, as: SendMessageResult.self)
            if let index = messages.firstIndex(where: { $0.clientId == clientID }) {
                messages[index] = result.message
            } else {
                messages.append(result.message)
            }
            local?.upsert(result.message)
            try? await markRead(upTo: result.message.id)
        } catch {
            errorText = (error as? APIError)?.message ?? "Image message failed."
        }
    }

    func castMessage(_ message: MessageOut) {
        if !messages.contains(where: { $0.id == message.id }) {
            messages.append(message)
            messages.sort { $0.sentAt < $1.sentAt }
        }
    }

    func react(messageID: String, emoji: String) async {
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/conversations/\(conversationID)/messages/\(messageID)/react",
            method: .post,
            body: ["emoji": emoji]
        )
        _ = try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())
    }

    func toggleReaction(message: MessageOut, emoji: String) async {
        let mine = (message.reactions?[emoji] ?? []).contains(SessionStore.shared.currentUserID ?? "")
        if mine {
            let builder = URLRequestBuilder(
                base: client.baseURL,
                path: "/v1/conversations/\(conversationID)/messages/\(message.id)/react/\(emoji)",
                method: .delete
            )
            _ = try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())
        } else {
            await react(messageID: message.id, emoji: emoji)
        }
    }

    func edit(messageID: String, body: String) async {
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/conversations/\(conversationID)/messages/\(messageID)",
            method: .patch,
            body: ["body": body]
        )
        if let updated: MessageOut = try? await client.send(builder, as: MessageOut.self),
           let index = messages.firstIndex(where: { $0.id == messageID }) {
            messages[index] = updated
            local?.upsert(updated)
        }
    }

    func delete(messageID: String, forEveryone: Bool) async {
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/conversations/\(conversationID)/messages/\(messageID)",
            method: .delete,
            body: ["delete_for": forEveryone ? "everyone" : "me"]
        )
        _ = try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())
        if !forEveryone, let index = messages.firstIndex(where: { $0.id == messageID }) {
            messages.remove(at: index)
        } else if let index = messages.firstIndex(where: { $0.id == messageID }) {
            messages[index] = MessageOut(
                id: messageID, conversationId: conversationID, senderId: messages[index].senderId,
                body: nil, clientId: messages[index].clientId, sentAt: messages[index].sentAt,
                isEdited: false, status: "deleted", attachments: []
            )
        }
    }
}