import SwiftUI
import Observation

struct NotificationPreferences: Decodable {
    var messagesEnabled: Bool
    var groupsEnabled: Bool
    var callsEnabled: Bool
    var streakNotifications: Bool
    var streakReminders: Bool
    var friendRequests: Bool
    var securityAlerts: Bool
    var showPreview: Bool
    var quietHoursEnabled: Bool

    enum CodingKeys: String, CodingKey {
        case messagesEnabled = "messages_enabled"
        case groupsEnabled = "groups_enabled"
        case callsEnabled = "calls_enabled"
        case streakNotifications = "streak_notifications"
        case streakReminders = "streak_reminders"
        case friendRequests = "friend_requests"
        case securityAlerts = "security_alerts"
        case showPreview = "show_preview"
        case quietHoursEnabled = "quiet_hours_enabled"
    }
}

@Observable
final class NotificationPreferencesStore {
    var prefs: NotificationPreferences?

    private let client = APIClient.shared

    func load() async {
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/notifications/preferences")
        prefs = try? await client.send(builder, as: NotificationPreferences.self, defaultValue: nil)
    }

    func update(_ patch: NotificationPreferencesPatch) async {
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/notifications/preferences", method: .patch, body: patch)
        if let updated: NotificationPreferences = try? await client.send(builder, as: NotificationPreferences.self, defaultValue: nil) {
            prefs = updated
        }
    }
}

struct NotificationPreferencesPatch: Encodable {
    var messagesEnabled: Bool?
    var groupsEnabled: Bool?
    var callsEnabled: Bool?
    var friendRequests: Bool?
    var showPreview: Bool?

    enum CodingKeys: String, CodingKey {
        case messagesEnabled = "messages_enabled"
        case groupsEnabled = "groups_enabled"
        case callsEnabled = "calls_enabled"
        case friendRequests = "friend_requests"
        case showPreview = "show_preview"
    }
}