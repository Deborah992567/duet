import SwiftUI

struct ChatView: View {
    let conversation: ConversationSummary
    @State private var store: ChatMessageStore
    @State private var realtime = RealtimeClient()
    @State private var draft = ""
    @State private var errorText: String?

    init(conversation: ConversationSummary) {
        self.conversation = conversation
        _store = State(initialValue: ChatMessageStore(conversationID: conversation.id))
    }

    var body: some View {
        VStack(spacing: 0) {
            streakBanner
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: Theme.Metrics.small) {
                        if store.messages.isEmpty {
                            ChatEmptyState()
                        }
                        ForEach(store.messages) { message in
                            MessageBubble(
                                message: message,
                                isOutgoing: message.senderId == SessionStore.shared.currentUserID
                            )
                            .id(message.id)
                        }
                    }
                    .padding(Theme.Metrics.padding)
                }
                .onChange(of: store.messages.count) {
                    if let last = store.messages.last {
                        withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo(last.id, anchor: .bottom) }
                    }
                }
            }
            composer
        }
        .background(Theme.Palette.background)
        .navigationTitle(conversation.name ?? conversation.peer?.username ?? "Chat")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await store.loadHistory()
            realtime.onEnvelope = { type, data in
                if type == "message.created",
                   let data, let payload = try? JSONDecoder.api.decode(MessageOut.self, from: data) {
                    store.castMessage(payload)
                }
            }
            realtime.connect(conversationIDs: [conversation.id])
        }
        .onDisappear { realtime.disconnect() }
    }

    private var streakBanner: some View {
        Group {
            if conversation.streakAlive || conversation.currentStreak > 0 {
                HStack(spacing: 6) {
                    Image(systemName: "flame.fill")
                        .foregroundStyle(Theme.Palette.flameOn)
                    Text(flameLabel)
                        .font(.subheadline.bold())
                        .foregroundStyle(Theme.Palette.textPrimary)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 8)
                .background(Theme.Palette.bubbleIncoming)
            }
        }
    }

    private var flameLabel: String {
        if conversation.currentStreak == 1 { return "1 day streak — keep it going" }
        return "\(conversation.currentStreak)-day streak"
    }

    private var composer: some View {
        HStack(spacing: Theme.Metrics.small) {
            TextField("Message", text: $draft, axis: .vertical)
                .lineLimit(1...4)
                .padding(.horizontal, Theme.Metrics.padding)
                .padding(.vertical, 10)
                .background(Theme.Palette.surface)
                .clipShape(RoundedRectangle(cornerRadius: Theme.Metrics.radiusSmall, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: Theme.Metrics.radiusSmall, style: .continuous)
                        .stroke(Theme.Palette.outline, lineWidth: Theme.Metrics.lineWidth)
                )
            Button {
                send()
            } label: {
                Image(systemName: "arrow.up.circle.fill")
                    .font(.system(size: 34))
                    .foregroundStyle(draft.trimmingCharacters(in: .whitespaces).isEmpty ? Theme.Palette.flameOff : Theme.Palette.brand)
            }
            .disabled(draft.trimmingCharacters(in: .whitespaces).isEmpty)
        }
        .padding(Theme.Metrics.padding)
        .background(Theme.Palette.surface)
        .overlay(alignment: .top) {
            Rectangle().fill(Theme.Palette.outline).frame(height: Theme.Metrics.lineWidth)
        }
    }

    private func send() {
        let body = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty else { return }
        let clientID = UUID().uuidString.lowercased()
        draft = ""
        Task { await store.send(body: body, clientID: clientID) }
    }
}

struct ChatEmptyState: View {
    var body: some View {
        VStack(spacing: Theme.Metrics.small) {
            Image(systemName: "sparkles")
                .font(.system(size: 40))
                .foregroundStyle(Theme.Palette.brand)
            Text("No messages yet")
                .font(Theme.Typography.headline)
            Text("Send the first message — streaks count both sides the same day.")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.textSecondary)
                .multilineTextAlignment(.center)
        }
        .padding(Theme.Metrics.padding * 3)
    }
}

struct MessageBubble: View {
    let message: MessageOut
    let isOutgoing: Bool

    var body: some View {
        HStack {
            if isOutgoing { Spacer(minLength: 48) }
            VStack(alignment: isOutgoing ? .trailing : .leading, spacing: 3) {
                Text(message.body ?? "Message deleted")
                    .font(Theme.Typography.body)
                    .foregroundStyle(isOutgoing ? .white : Theme.Palette.textPrimary)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 9)
                    .background(isOutgoing ? Theme.Palette.bubbleOutgoing : Theme.Palette.bubbleIncoming)
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                HStack(spacing: 4) {
                    Text(timeLabel)
                        .font(.caption2)
                        .foregroundStyle(Theme.Palette.textSecondary)
                    if isOutgoing {
                        Image(systemName: message.status == "read" ? "checkmark.circle.fill" : "checkmark")
                            .font(.caption2)
                            .foregroundStyle(message.status == "read" ? Theme.Palette.brand : Theme.Palette.textSecondary)
                    }
                }
            }
            if !isOutgoing { Spacer(minLength: 48) }
        }
    }

    private var timeLabel: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: message.sentAt)
    }
}