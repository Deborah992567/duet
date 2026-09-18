import SwiftUI

struct ProfileView: View {
    @Environment(AppState.self) private var state
    @Environment(LocalStore.self) private var local
    @State private var settings = SettingsStore()
    @State private var showClearConfirm = false

    private var appVersion: String {
        let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
        let build = Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
        return "\(version) (\(build))"
    }

    private func signOut() {
        SessionStore.shared.clear()
        RealtimeClient().disconnect()
        PushRegistration.unregister()
        state.isSignedIn = false
    }

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

                Section("Account") {
                    Button {
                        signOut()
                    } label: {
                        HStack {
                            Label("Sign out", systemImage: "rectangle.portrait.and.arrow.right")
                                .foregroundStyle(Theme.Palette.danger)
                            Spacer()
                        }
                    }
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
                    LabeledContent("Version", value: appVersion)
                    NavigationLink("Toast privacy policy") { PrivacyPolicyView() }
                    NavigationLink("Terms of service") { TermsView() }
                }

                Section("Storage") {
                    Button(role: .destructive) {
                        showClearConfirm = true
                    } label: {
                        Label("Clear local messages & drafts", systemImage: "trash")
                    }
                    .confirmationDialog("Clear all cached conversations, messages and pending drafts?", isPresented: $showClearConfirm, titleVisibility: .visible) {
                        Button("Clear local data", role: .destructive) { local.clearAll() }
                    }
                }

                Section {
                    Button {
                        signOut()
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