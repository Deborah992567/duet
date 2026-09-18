import SwiftUI

/// Root view. Routes to onboarding when signed out, tabs when signed in.
struct RootView: View {
    @Environment(AppState.self) private var state

    var body: some View {
        Group {
            if state.isSignedIn {
                MainTabView()
            } else {
                LoginView()
            }
        }
        .animation(.easeInOut(duration: 0.2), value: state.isSignedIn)
    }
}