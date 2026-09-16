import SwiftUI

struct ProfileView: View {
    @Environment(AppState.self) private var state

    var body: some View {
        NavigationStack {
            List {
                Section("Account") {
                    Label("Streak settings", systemImage: "flame.fill")
                        .foregroundStyle(Theme.Palette.textPrimary)
                    Label("Notification preferences", systemImage: "bell.fill")
                        .foregroundStyle(Theme.Palette.textPrimary)
                }
                Section {
                    Button {
                        SessionStore.shared.clear()
                        state.isSignedIn = false
                    } label: {
                        Text("Sign out")
                            .foregroundStyle(Theme.Palette.danger)
                    }
                }
            }
            .background(Theme.Palette.background)
            .scrollContentBackground(.hidden)
            .navigationTitle("Profile")
        }
    }
}