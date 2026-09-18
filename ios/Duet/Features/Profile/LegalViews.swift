import SwiftUI

/// Legal placeholders. Product is pre-launch; policies are finalized before release.
struct PrivacyPolicyView: View {
    var body: some View { LegalTextView(title: "Privacy Policy", content: policyText) }
}

struct TermsView: View {
    var body: some View { LegalTextView(title: "Terms of Service", content: termsText) }
}

private let policyText = """
Duet Privacy Policy

We keep your messages between you and the people you send them to. \
Read receipts, delivery status, and presence indicators are shared only within the conversations you take part in.

Streak information (current streak, milestones, and whether you are active) is shown to the friends you share a \
direct conversation with. You can hide your streaks at any time in Profile → Streak preferences.

We do not sell your personal data. Access tokens are stored in the iOS Keychain on your device.

This policy is finalized before the public release.
"""

private let termsText = """
Duet Terms of Service

Use Duet for lawful, respectful messaging. Spam, harassment, and exploitation are prohibited and may lead to \
account termination.

Streaks are a game mechanic: both participants must send at least one message on the same calendar day. Streaks are \
not contractual commitments and can end automatically when a day is missed.

Tap-to-text calling features are activated when available in your region.

This policy is finalized before the public release.
"""

struct LegalTextView: View {
    let title: String
    let content: String

    var body: some View {
        ScrollView {
            Text(content)
                .font(Theme.Typography.body)
                .foregroundStyle(Theme.Palette.textPrimary)
                .lineSpacing(4)
                .padding(Theme.Metrics.padding)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .background(Theme.Palette.background)
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
    }
}