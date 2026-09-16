import SwiftUI

/// Streaks tab: list of active streak rounds with a flame tile per conversation.
struct StreaksView: View {
    var body: some View {
        NavigationStack {
            VStack(spacing: Theme.Metrics.padding) {
                Image(systemName: "flame.fill")
                    .font(.system(size: 56))
                    .foregroundStyle(Theme.Palette.flameOn)
                Text("No active streaks yet")
                    .font(Theme.Typography.headline)
                Text("Both of you send a message the same day on the app to light this up.")
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Palette.textSecondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.horizontal, Theme.Metrics.padding * 2)
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Theme.Palette.background)
            .navigationTitle("Streaks")
        }
    }
}