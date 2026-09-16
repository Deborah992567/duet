import SwiftUI

@main
struct EnvyChatApp: App {
    @State private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(appState)
                .preferredColorScheme(.light)
        }
    }
}

@Observable
final class AppState {
    var isSignedIn = false
    var currentUserID: String?

    static let shared = AppState()
}