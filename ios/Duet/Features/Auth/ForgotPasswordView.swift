import SwiftUI

struct ForgotPasswordView: View {
    @State private var email = ""
    @State private var sent = false
    @State private var isSubmitting = false
    @State private var errorText: String?

    var body: some View {
        VStack(spacing: Theme.Metrics.padding) {
            if sent {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 56))
                    .foregroundStyle(Theme.Palette.success)
                Text("Check your inbox")
                    .font(Theme.Typography.headline)
                Text("We sent a reset link to \(email). Use it to choose a new password.")
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Palette.textSecondary)
                    .multilineTextAlignment(.center)
            } else {
                Text("Reset your password")
                    .font(Theme.Typography.title)
                TextField("Email", text: $email)
                    .textInputAutocapitalization(.never)
                    .keyboardType(.emailAddress)
                    .padding(Theme.Metrics.padding)
                    .cardStyle()

                if let errorText {
                    Text(errorText)
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.danger)
                }

                Button {
                    sendReset()
                } label: {
                    Text(isSubmitting ? "Sending…" : "Send reset link")
                        .font(Theme.Typography.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Theme.Metrics.padding)
                        .background(Theme.Palette.brand)
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.Metrics.radius, style: .continuous))
                }
                .disabled(isSubmitting || email.isEmpty)
            }
            Spacer()
        }
        .padding(Theme.Metrics.padding)
        .background(Theme.Palette.background)
    }

    private func sendReset() {
        isSubmitting = true
        errorText = nil
        Task {
            do {
                try await AuthViewStore.shared.requestPasswordReset(email: email)
                await MainActor.run { sent = true }
            } catch {
                await MainActor.run {
                    errorText = (error as? APIError)?.message ?? "Could not send reset link."
                }
            }
            await MainActor.run { isSubmitting = false }
        }
    }
}