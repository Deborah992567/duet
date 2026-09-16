import Foundation
import Observation

@Observable
final class SettingsStore {
    var streakVisible = true
    var notificationsEnabled = true
    var remindersEnabled = true
    var freezesEnabled = false
    var isSaving = false
    var saved = false

    private let client = APIClient.shared

    func push() async {
        isSaving = true
        defer { isSaving = false }
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/streaks/me/settings",
            method: .patch,
            body: [
                "visible": streakVisible,
                "notifications_enabled": notificationsEnabled,
                "reminders_enabled": remindersEnabled,
                "freezes_enabled": freezesEnabled,
            ]
        )
        if (try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())) != nil {
            saved = true
        }
        try? await Task.sleep(nanoseconds: 1_500_000_000)
        saved = false
    }
}