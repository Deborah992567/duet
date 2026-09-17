import Foundation
import UserNotifications
import Observation

/// Authorization + APNs token registration seam. On simulator there is no device
/// token, so registration becomes a no-op until a real device is provisioned.
@MainActor
@Observable
final class PushRegistration {
    static let shared = PushRegistration()

    var authorized = false

    func authorizeAndRegister() async {
        let granted = await requestAuthorization()
        authorized = granted
        guard granted, !registeredToken else { return }
        let token = await fetchDeviceToken()
        guard let token else { return }
        await sendToken(token)
    }

    func requestAuthorization() async -> Bool {
        let center = UNUserNotificationCenter.current()
        do {
            return try await center.requestAuthorization(options: [.alert, .sound, .badge])
        } catch {
            return false
        }
    }

    private var registeredToken: Bool {
        UserDefaults.standard.bool(forKey: "push.token_registered")
    }

    private func fetchDeviceToken() async -> String? {
        // On-device only: UIApplication.shared.registerForRemoteNotifications()
        // delivers a device token to the app delegate. Simulators return nil.
        nil
    }

    private func sendToken(_ token: String) async {
        let client = APIClient.shared
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/notifications/push-token",
            method: .post,
            body: ["token": token, "platform": "ios"]
        )
        guard (try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())) != nil else { return }
        UserDefaults.standard.set(true, forKey: "push.token_registered")
    }
}