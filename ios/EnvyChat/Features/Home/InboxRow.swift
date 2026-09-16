import SwiftUI

struct InboxRow: View {
    let conversation: ConversationSummary

    var body: some View {
        HStack(spacing: Theme.Metrics.padding) {
            avatar
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(title)
                        .font(Theme.Typography.headline)
                        .foregroundStyle(Theme.Palette.textPrimary)
                        .lineLimit(1)
                    if conversation.isPinned {
                        Image(systemName: "pin.fill")
                            .font(.caption2)
                            .foregroundStyle(Theme.Palette.textSecondary)
                    }
                }
                HStack(spacing: 4) {
                    if conversation.isMuted {
                        Image(systemName: "bell.slash.fill")
                            .font(.caption2)
                            .foregroundStyle(Theme.Palette.textSecondary)
                    }
                    Text(conversation.lastMessagePreview ?? "Say hi to start a streak")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.textSecondary)
                        .lineLimit(1)
                }
            }
            Spacer()
            VStack(alignment: .trailing, spacing: 4) {
                if conversation.streakAlive || conversation.currentStreak > 0 {
                    HStack(spacing: 3) {
                        Image(systemName: "flame.fill")
                            .foregroundStyle(Theme.Palette.flameOn)
                        Text("\(conversation.currentStreak)")
                            .font(.system(size: 13, weight: .bold))
                            .foregroundStyle(Theme.Palette.flameOn)
                    }
                } else {
                    Image(systemName: "flame")
                        .font(.caption2)
                        .foregroundStyle(Theme.Palette.flameOff)
                }
                if conversation.unreadCount > 0 {
                    Text("\(conversation.unreadCount)")
                        .font(.caption.bold())
                        .foregroundStyle(.white)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 2)
                        .background(Theme.Palette.brand)
                        .clipShape(Capsule())
                }
            }
        }
        .padding(Theme.Metrics.padding)
        .cardStyle()
    }

    private var title: String {
        conversation.name ?? conversation.peer?.displayName ?? conversation.peer?.username ?? "Conversation"
    }

    private var avatar: some View {
        ZStack {
            Circle()
                .fill(Theme.Palette.bubbleIncoming)
                .frame(width: 52, height: 52)
            Image(systemName: "person.fill")
                .font(.title3)
                .foregroundStyle(Theme.Palette.textSecondary)
        }
    }
}