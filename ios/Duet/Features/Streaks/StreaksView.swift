import SwiftUI

/// Streaks tab: shows all direct conversations that currently have a live streak,
/// using the conversations list (which already carries current_streak / streak_alive).
struct StreaksView: View {
    @State private var store = ConversationListStore()
    @State private var path = NavigationPath()

    private var streakConversations: [ConversationSummary] {
        let direct = store.conversations.filter { $0.type == "direct" }
        let active = direct.filter { $0.currentStreak > 0 || $0.streakAlive }
        return active.sorted { $0.currentStreak > $1.currentStreak }
    }

    var body: some View {
        NavigationStack(path: $path) {
            streaksPage
        }
    }

    private var streaksPage: some View {
        content
            .background(Theme.Palette.background)
            .navigationTitle("Streaks")
            .navigationBarTitleDisplayMode(.large)
            .navigationDestination(for: ConversationSummary.self) { conversation in
                ChatView(conversation: conversation)
            }
            .onAppear {
                Task { await store.refresh() }
            }
    }

    @ViewBuilder
    private var content: some View {
        ScrollView {
            VStack(spacing: Theme.Metrics.padding) {
                header
                tileList
            }
            .padding(.vertical, Theme.Metrics.small)
        }
    }

    @ViewBuilder
    private var tileList: some View {
        if store.isLoading && streakConversations.isEmpty {
            ProgressView()
                .tint(Theme.Palette.brand)
                .padding()
        } else if streakConversations.isEmpty {
            emptyState
        } else {
            LazyVStack(spacing: Theme.Metrics.padding) {
                ForEach(streakConversations) { conversation in
                    NavigationLink(value: conversation) {
                        StreakTileView(conversation: conversation)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, Theme.Metrics.padding)
        }
    }

    private var header: some View {
        HStack {
            Text("Flame leaderboard")
                .font(Theme.Typography.headline)
                .foregroundStyle(Theme.Palette.textPrimary)
            Spacer()
            Image(systemName: "flame.fill")
                .foregroundStyle(Theme.Palette.flameOn)
        }
        .padding(.horizontal, Theme.Metrics.padding)
    }

    private var emptyState: some View {
        VStack(spacing: Theme.Metrics.padding) {
            Image(systemName: "flame")
                .font(.system(size: 56))
                .foregroundStyle(Theme.Palette.flameOff)
            Text("No streaks yet")
                .font(Theme.Typography.headline)
                .foregroundStyle(Theme.Palette.textPrimary)
            Text("Start a conversation and both send a message on the same day to light the first flame.")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, Theme.Metrics.padding * 2)
        }
        .padding(.top, 60)
    }
}

struct StreakTileView: View {
    let conversation: ConversationSummary

    var body: some View {
        HStack(spacing: Theme.Metrics.padding) {
            ZStack {
                Circle()
                    .fill(Theme.Palette.bubbleIncoming)
                    .frame(width: 48, height: 48)
                Image(systemName: "flame.fill")
                    .font(.system(size: 22))
                    .foregroundStyle(conversation.streakAlive ? Theme.Palette.flameOn : Theme.Palette.flameOff)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(conversation.name ?? conversation.peer?.username ?? "Streak")
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Palette.textPrimary)
                Text("\(conversation.currentStreak) day\(conversation.currentStreak == 1 ? "" : "s") alive")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(conversation.streakAlive ? Theme.Palette.brand : Theme.Palette.flameOff)
            }
            Spacer()

            Text("\(conversation.currentStreak)")
                .font(.system(size: 28, weight: .heavy, design: .rounded))
                .foregroundStyle(conversation.streakAlive ? Theme.Palette.flameOn : Theme.Palette.textSecondary)
        }
        .padding(Theme.Metrics.padding)
        .cardStyle()
    }
}