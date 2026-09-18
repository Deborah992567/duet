import SwiftUI
import Observation

/// Tracks who is currently typing (from WS `typing` events), keyed by conversation id.
@Observable
final class TypingStore {
    private var typingConversations: Set<String> = []
    private let realtime = RealtimeClient()

    func start() {
        realtime.onEnvelope = { [weak self] type, data in
            guard let self, type == "typing", let data else { return }
            guard let object = try? JSONDecoder.api.decode([String: String].self, from: data) else { return }
            if let conversationID = object["conversation_id"], let value = object["typing"] {
                let isTyping = value == "true" || value == "1"
                if isTyping {
                    self.typingConversations.insert(conversationID)
                } else {
                    self.typingConversations.remove(conversationID)
                }
            }
        }
    }

    func subscribe(conversationIDs: [String]) {
        realtime.subscribe(conversationIDs: conversationIDs)
    }

    func isTyping(in conversationID: String) -> Bool {
        typingConversations.contains(conversationID)
    }

    func stop() {
        realtime.disconnect()
    }
}