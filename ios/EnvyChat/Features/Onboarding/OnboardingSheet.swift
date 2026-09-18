import SwiftUI

/// First-run welcome sheet explaining the streak concept.
struct OnboardingSheet: View {
    var onDone: () -> Void

    var body: some View {
        VStack(spacing: Theme.Metrics.padding * 2) {
            Spacer()
            AnimatedFlame(size: 120, isAlive: true)
                .padding(.bottom, Theme.Metrics.padding)

            Text("Welcome to EnvyChat")
                .font(.system(size: 30, weight: .heavy, design: .rounded))
                .foregroundStyle(Theme.Palette.textPrimary)

            VStack(alignment: .leading, spacing: Theme.Metrics.padding) {
                tip(icon: "flame.fill", color: Theme.Palette.flameOn, title: "Keep the flame alive", detail: "Both of you send at least one message every day to keep a streak going.")
                tip(icon: "bolt.fill", color: Theme.Palette.brand, title: "Streak freezes", detail: "Missed a day? Freezes auto-protect your streak as it grows.")
                tip(icon: "figure.wave", color: Theme.Palette.brand, title: "Voice & images", detail: "Tap-to-talk voice messages and photos keep things personal.")
            }
            .padding(.horizontal, Theme.Metrics.padding)

            Button {
                UserDefaults.standard.set(true, forKey: "onboarding.done")
                onDone()
            } label: {
                Text("Get started")
                    .font(Theme.Typography.body.bold())
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(Theme.Palette.brand)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.Metrics.radius, style: .continuous))
                    .padding(.horizontal, Theme.Metrics.padding)
            }

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.Palette.background)
        .interactiveDismissDisabled()
    }

    private func tip(icon: String, color: Color, title: String, detail: String) -> some View {
        HStack(alignment: .top, spacing: Theme.Metrics.padding) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(color)
                .frame(width: 32)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(Theme.Typography.body.bold())
                    .foregroundStyle(Theme.Palette.textPrimary)
                Text(detail)
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.textSecondary)
            }
        }
    }
}