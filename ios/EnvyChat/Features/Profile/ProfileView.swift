import SwiftUI

struct ProfileView: View {
    @Environment(AppState.self) private var state
    @State private var settings = SettingsStore()

    var body: some View {
        NavigationStack {
            List {
                Section {
                    HStack(spacing: Theme.Metrics.padding) {
                        ZStack {
                            Circle()
                                .fill(Theme.Palette.bubbleIncoming)
                                .frame(width: 56, height: 56)
                            Image(systemName: "person.fill")
                                .foregroundStyle(Theme.Palette.brand)
                        }
                        VStack(alignment: .leading) {
                            Text("You")
                                .font(Theme.Typography.headline)
                                .foregroundStyle(Theme.Palette.textPrimary)
                            Text("EnvyChat")
                                .font(Theme.Typography.caption)
                                .foregroundStyle(Theme.Palette.textSecondary)
                        }
                    }
                    .padding(.vertical, 4)
                }

                Section("Streak preferences") {
                    Toggle("Show my streaks", isOn: $settings.streakVisible)
                        .onChange(of: settings.streakVisible) { _, _ in Task { await settings.push() } }
                    Toggle("Streak notifications", isOn: $settings.notificationsEnabled)
                        .onChange(of: settings.notificationsEnabled) { _, _ in Task { await settings.push() } }
                    Toggle("Daily streak reminders", isOn: $settings.remindersEnabled)
                        .onChange(of: settings.remindersEnabled) { _, _ in Task { await settings.push() } }
                    Toggle("Freeze protection", isOn: $settings.freezesEnabled)
                        .onChange(of: settings.freezesEnabled) { _, _ in Task { await settings.push() } }
                        .tint(Theme.Palette.brand)
                }

                Section("About") {
                    NavigationLink("Toast privacy policy") { PrivacyPolicyView() }
                    NavigationLink("Terms of service") { TermsView() }
                }

                Section {
                    Button {
                        SessionStore.shared.clear()
                        RealtimeClient().disconnect()
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