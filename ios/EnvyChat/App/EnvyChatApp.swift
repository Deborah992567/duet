import SwiftUI
import SwiftData

@main
struct EnvyChatApp: App {
    @State private var appState = AppState()
    @State private var localStore = LocalStore()
    private let realtime = RealtimeClient()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(appState)
                .environment(localStore)
                .preferredColorScheme(.light)
                .task {
                    // Reconnect the socket when a session already exists.
                    if appState.isSignedIn {
                        realtime.connect(conversationIDs: [])
                        await PushRegistration.shared.authorizeAndRegister()
                    }
                }
        }
        .modelContainer(localStore.container)
    }
}

@Observable
final class AppState {
    var isSignedIn = false
    var currentUserID: String?

    static let shared = AppState()
}