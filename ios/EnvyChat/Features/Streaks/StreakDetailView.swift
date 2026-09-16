import SwiftUI

/// Streak detail: animated flame + days + milestone chips. Flat, no gradients.
struct StreakDetailView: View {
    let conversation: ConversationSummary

    private let milestones = [7, 30, 100, 365, 500, 1000]

    var body: some View {
        VStack(spacing: Theme.Metrics.padding) {
            Spacer()
            AnimatedFlame(size: 120, isAlive: conversation.streakAlive || conversation.currentStreak > 0)
            Text("\(conversation.currentStreak)")
                .font(.system(size: 64, weight: .heavy, design: .rounded))
                .foregroundStyle(Theme.Palette.flameOn)
            Text(conversation.currentStreak == 1 ? "day on a roll" : "days on a roll")
                .font(Theme.Typography.headline)
                .foregroundStyle(Theme.Palette.textPrimary)

            VStack(spacing: Theme.Metrics.small) {
                ForEach(milestones, id: \.self) { milestone in
                    HStack {
                        Text("\(milestone)-day streak")
                            .font(Theme.Typography.body)
                            .foregroundStyle(Theme.Palette.textPrimary)
                        Spacer()
                        if conversation.currentStreak >= milestone {
                            Image(systemName: "checkmark.seal.fill")
                                .foregroundStyle(Theme.Palette.brand)
                        } else {
                            Text("\(milestone - conversation.currentStreak) days to go")
                                .font(Theme.Typography.caption)
                                .foregroundStyle(Theme.Palette.textSecondary)
                        }
                    }
                    .padding(Theme.Metrics.padding)
                    .cardStyle()
                }
            }
            .padding(.horizontal, Theme.Metrics.padding)

            Text("Both of you need to send at least one message every day. Missing a day ends the streak.")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, Theme.Metrics.padding * 2)

            Spacer()
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.Palette.background)
        .navigationTitle(conversation.name ?? conversation.peer?.username ?? "Streak")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct AnimatedFlame: View {
    let size: CGFloat
    let isAlive: Bool

    var body: some View {
        Image(systemName: "flame.fill")
            .font(.system(size: size))
            .foregroundStyle(isAlive ? Theme.Palette.flameOn : Theme.Palette.flameOff)
            .phaseAnimator([0, 1, 0]) { view, phase in
                view
                    .scaleEffect(isAlive ? 1 + 0.06 * phase : 1)
                    .offset(y: isAlive ? -3 * phase : 0)
            } animation: { _ in
                .easeInOut(duration: 0.8)
            }
    }
}