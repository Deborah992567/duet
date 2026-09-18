import SwiftUI
import Observation

/// Tracks peers who are online (from WS `presence.changed` events), keyed by user id.
@Observable
final class PresenceStore {
    private(set) var onlineUsers: Set<String> = []
    private let realtime = RealtimeClient()

    func start() {
        realtime.onEnvelope = { [weak self] type, data in
            guard let self, type == "presence.changed", let data else { return }
            guard let object = try? JSONDecoder.api.decode([String: String].self, from: data) else { return }
            guard let userID = object["user_id"] else { return }
            let isOnline = object["status"] == "online"
            if isOnline {
                self.onlineUsers.insert(userID)
            } else {
                self.onlineUsers.remove(userID)
            }
        }
    }

    func subscribe(conversationIDs: [String]) {
        realtime.subscribe(conversationIDs: conversationIDs)
    }

    func isOnline(userID: String?) -> Bool {
        guard let userID else { return false }
        return onlineUsers.contains(userID)
    }

    func stop() {
        realtime.disconnect()
    }
}