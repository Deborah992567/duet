import SwiftUI

struct LoginView: View {
    @Environment(AppState.self) private var state
    @State private var email = ""
    @State private var password = ""
    @State private var isSubmitting = false
    @State private var errorText: String?
    @State private var showRegister = false
    @State private var showForgot = false

    var body: some View {
        NavigationStack {
            content
                .navigationDestination(isPresented: $showRegister) {
                    RegisterView()
                }
                .navigationDestination(isPresented: $showForgot) {
                    ForgotPasswordView()
                }
        }
    }

    private var content: some View {
        VStack(spacing: Theme.Metrics.padding) {
            Spacer()
            Image(systemName: "flame.fill")
                .font(.system(size: 64))
                .foregroundStyle(Theme.Palette.flameOn)
            Text("EnvyChat")
                .font(Theme.Typography.title)
                .foregroundStyle(Theme.Palette.textPrimary)
            Text("Stay on a roll with the people who matter.")
                .font(Theme.Typography.body)
                .foregroundStyle(Theme.Palette.textSecondary)

            VStack(spacing: Theme.Metrics.small) {
                TextField("Email or username", text: $email)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.emailAddress)
                    .padding(Theme.Metrics.padding)
                    .cardStyle()
                SecureField("Password", text: $password)
                    .padding(Theme.Metrics.padding)
                    .cardStyle()
            }
            .padding(.top, Theme.Metrics.padding)

            if let errorText {
                Text(errorText)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.danger)
                    .multilineTextAlignment(.center)
            }

            Button {
                signIn()
            } label: {
                Text(isSubmitting ? "Signing in…" : "Sign in")
                    .font(Theme.Typography.headline)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Theme.Metrics.padding)
                    .background(Theme.Palette.brand)
                    .foregroundStyle(.white)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.Metrics.radius, style: .continuous))
            }
            .disabled(isSubmitting)

            Button("Create an account") {
                showRegister = true
            }
            .font(Theme.Typography.body)
            .foregroundStyle(Theme.Palette.brand)

            Button("Forgot password?") {
                showForgot = true
            }
            .font(Theme.Typography.caption)
            .foregroundStyle(Theme.Palette.textSecondary)

            Spacer()

            Text("By continuing, you agree to the EnvyChat terms.")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.textSecondary)
        }
        .padding(Theme.Metrics.padding)
        .background(Theme.Palette.background)
    }

    private func signIn() {
        guard !email.isEmpty, !password.isEmpty else {
            errorText = "Enter your email and password."
            return
        }
        isSubmitting = true
        errorText = nil
        Task {
            do {
                try await AuthViewStore.shared.signIn(identifier: email, password: password)
                await MainActor.run { state.isSignedIn = true }
            } catch {
                await MainActor.run {
                    errorText = (error as? LocalizedError)?.errorDescription ?? "Sign in failed."
                }
            }
            await MainActor.run { isSubmitting = false }
        }
    }
}