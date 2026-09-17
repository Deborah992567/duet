import SwiftUI

struct RegisterView: View {
    @Environment(AppState.self) private var state
    @State private var email = ""
    @State private var username = ""
    @State private var displayName = ""
    @State private var password = ""
    @State private var isSubmitting = false
    @State private var errorText: String?
    var onDone: () -> Void = {}

    var body: some View {
        VStack(spacing: Theme.Metrics.padding) {
            Text("Create your account")
                .font(Theme.Typography.title)
                .foregroundStyle(Theme.Palette.textPrimary)

            VStack(spacing: Theme.Metrics.small) {
                TextField("Email", text: $email)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.emailAddress)
                    .padding(Theme.Metrics.padding)
                    .cardStyle()
                TextField("Username", text: $username)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .padding(Theme.Metrics.padding)
                    .cardStyle()
                TextField("Display name (optional)", text: $displayName)
                    .padding(Theme.Metrics.padding)
                    .cardStyle()
                SecureField("Password", text: $password)
                    .padding(Theme.Metrics.padding)
                    .cardStyle()
            }

            if let errorText {
                Text(errorText)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.danger)
            }

            Button {
                register()
            } label: {
                Text(isSubmitting ? "Creating account…" : "Create account")
                    .font(Theme.Typography.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Metrics.padding)
                    .background(Theme.Palette.brand)
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.Metrics.radius, style: .continuous))
            }
            .disabled(isSubmitting)

            Spacer()
        }
        .padding(Theme.Metrics.padding)
        .background(Theme.Palette.background)
    }

    private func register() {
        guard !email.isEmpty, !username.isEmpty, password.count >= 8 else {
            errorText = "Use a valid email, a username, and a password with 8+ characters."
            return
        }
        isSubmitting = true
        errorText = nil
        Task {
            do {
                try await AuthViewStore.shared.register(
                    email: email, username: username,
                    displayName: displayName.isEmpty ? username : displayName,
                    password: password
                )
                await MainActor.run {
                    state.isSignedIn = true
                    Task { await PushRegistration.shared.authorizeAndRegister() }
                }
            } catch {
                await MainActor.run {
                    errorText = (error as? APIError)?.message ?? "Registration failed."
                }
            }
            await MainActor.run { isSubmitting = false }
        }
    }
}