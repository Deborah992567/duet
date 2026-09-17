import SwiftUI
import AVFoundation
import PhotosUI

struct ChatView: View {
    let conversation: ConversationSummary
    @State private var store: ChatMessageStore
    @State private var realtime = RealtimeClient()
    @State private var draft = ""
    @State private var errorText: String?
    @State private var showStreak = false
    @State private var recorder = VoiceRecorder()
    @State private var editingMessage: MessageOut?
    @State private var pickedImage: PhotosPickerItem?
    @State private var peerOnline = false
    @State private var typingCooldown = Date.distantPast
    @Environment(LocalStore.self) private var local

    init(conversation: ConversationSummary) {
        self.conversation = conversation
        _store = State(initialValue: ChatMessageStore(conversationID: conversation.id, local: nil))
    }

    var body: some View {
        VStack(spacing: 0) {
            streakBanner
            messagesList
            composer
        }
        .background(Theme.Palette.background)
        .navigationTitle(conversation.name ?? conversation.peer?.username ?? "Chat")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                if conversation.type == "direct" {
                    HStack(spacing: 5) {
                        Circle()
                            .fill(peerOnline ? Theme.Palette.success : Theme.Palette.flameOff)
                            .frame(width: 9, height: 9)
                        Text(peerOnline ? "Online" : "Offline")
                            .font(Theme.Typography.caption)
                            .foregroundStyle(Theme.Palette.textSecondary)
                    }
                }
            }
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Menu {
                        Text("Reactions")
                        ForEach(["❤️", "🔥", "😂", "👍", "😮"], id: \.self) { emoji in
                            Button("React \(emoji)") { Task { await lastMessageReact(emoji) } }
                        }
                    } label: {
                        Label("Quick react", systemImage: "face.smiling")
                    }
                    ConversationActionsMenu(conversation: conversation)
                } label: {
                    Image(systemName: "ellipsis.circle")
                        .foregroundStyle(Theme.Palette.brand)
                }
            }
        }
        .task {
            store.bind(local)
            store.hydrate(from: local.queuedMessages(in: conversation.id))
            await store.loadHistory()
            realtime.onEnvelope = { type, data in
                if type == "message.created",
                   let data, let payload = try? JSONDecoder.api.decode(MessageOut.self, from: data) {
                    store.castMessage(payload)
                    local.upsert(payload)
                } else if type == "presence.changed",
                          let data,
                          let presence = try? JSONDecoder.api.decode([String: String].self, from: data),
                          presence["user_id"] == conversation.peer?.id {
                    peerOnline = presence["status"] == "online"
                }
            }
            realtime.connect(conversationIDs: [conversation.id])
            await retryOutbox()
            recorder.onFinished = { url in
                Task {
                    let duration = Int((try? AVAudioPlayer(contentsOf: url))?.duration ?? 0) * 1000
                    await store.sendVoiceIfNeeded(recordedAt: url, durationMs: duration, uploader: MediaUploader())
                }
            }
        }
        .onDisappear {
            realtime.disconnect()
            Task { await emitTyping(false) }
        }
        .sheet(item: $editingMessage) { message in
            EditMessageSheet(message: message, store: store)
        }
    }

    private var messagesList: some View {
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
                        .contextMenu {
                            MessageActionsMenu(message: message, store: store) {
                                editingMessage = message
                            }
                        }
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
    }

    private var streakBanner: some View {
        Group {
            if conversation.streakAlive || conversation.currentStreak > 0 {
                Button {
                    showStreak = true
                } label: {
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
                .buttonStyle(.plain)
                .sheet(isPresented: $showStreak) {
                    NavigationStack {
                        StreakDetailView(conversation: conversation)
                            .toolbar { CloseToolbarButton { showStreak = false } }
                    }
                }
            }
        }
    }

    private var flameLabel: String {
        if conversation.currentStreak == 1 { return "1 day streak — keep it going" }
        return "\(conversation.currentStreak)-day streak"
    }

    private func lastMessageReact(_ emoji: String) {
        guard let last = store.messages.last else { return }
        Task { await store.react(messageID: last.id, emoji: emoji) }
    }

    private func emitTyping(_ typing: Bool) async {
        let now = Date()
        if typing && now.timeIntervalSince(typingCooldown) < 2.5 { return }
        typingCooldown = now
        let client = APIClient.shared
        if typing {
            let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversation.id)/typing", method: .post)
            _ = try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())
        } else {
            let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversation.id)/typing", method: .delete)
            _ = try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())
        }
    }

    private var composer: some View {
        HStack(spacing: Theme.Metrics.small) {
            PhotosPicker(selection: $pickedImage, matching: .images) {
                Image(systemName: "photo.on.rectangle")
                    .font(.system(size: 22))
                    .foregroundStyle(Theme.Palette.brand)
            }
            .onChange(of: pickedImage) { _, item in
                guard let item else { return }
                Task {
                    if let data = try? await item.loadTransferable(type: Data.self) {
                        let url = FileManager.default.temporaryDirectory.appendingPathComponent("img-\(UUID().uuidString).jpg")
                        try? data.write(to: url)
                        await store.sendImageIfNeeded(url: url, uploader: MediaUploader())
                    }
                }
            }
            TextField("Message", text: $draft, axis: .vertical)
                .lineLimit(1...4)
                .onChange(of: draft) { _, newValue in
                    let typing = !newValue.trimmingCharacters(in: .whitespaces).isEmpty
                    Task { await emitTyping(typing) }
                }
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

            TalkButton(recorder: recorder)
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
        Task {
            let didSend = await store.send(body: body, clientID: clientID)
            if !didSend {
                local.enqueue(conversationID: conversation.id, body: body)
            }
        }
    }

    private func retryOutbox() async {
        for entry in local.pendingOutbox() where entry.conversationID == conversation.id {
            let sent = await store.send(body: entry.body, clientID: entry.clientID)
            if sent { local.flush(entry) }
        }
    }
}

struct MessageActionsMenu: View {
    let message: MessageOut
    let store: ChatMessageStore
    var onEdit: (() -> Void)?

    var body: some View {
        ForEach(["❤️", "🔥", "😂", "👍", "😮"], id: \.self) { emoji in
            Button {
                Task { await store.react(messageID: message.id, emoji: emoji) }
            } label: {
                Label("React \(emoji)", systemImage: "face.smiling")
            }
        }
        Divider()
        if message.senderId == SessionStore.shared.currentUserID {
            Button(action: { onEdit?() }) {
                Label("Edit", systemImage: "square.and.pencil")
            }
            Button(role: .destructive) {
                Task { await store.delete(messageID: message.id, forEveryone: true) }
            } label: {
                Label("Delete for everyone", systemImage: "trash")
            }
        }
        Button(role: .destructive) {
            Task { await store.delete(messageID: message.id, forEveryone: false) }
        } label: {
            Label("Delete for me", systemImage: "trash.slash")
        }
    }
}

struct ConversationActionsMenu: View {
    let conversation: ConversationSummary
    @State private var busy = false

    var body: some View {
        Button {
            mutate(conversation.isMuted ? "unmute" : "mute")
        } label: {
            Label(conversation.isMuted ? "Unmute" : "Mute", systemImage: conversation.isMuted ? "bell.fill" : "bell.slash")
        }
        Button {
            mutate(conversation.isPinned ? "unpin" : "pin")
        } label: {
            Label(conversation.isPinned ? "Unpin" : "Pin", systemImage: conversation.isPinned ? "pin.slash" : "pin")
        }
        Divider()
        Button(role: .destructive) {
            mutate("hide")
        } label: {
            Label("Hide conversation", systemImage: "trash")
        }
        .disabled(busy)
    }

    private func mutate(_ action: String) {
        busy = true
        let client = APIClient.shared
        switch action {
        case "mute":
            let b = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversation.id)/mute", method: .post, body: ["muted": true])
            Task { _ = try? await client.send(b, as: NoContent.self, defaultValue: NoContent()); busy = false }
        case "unmute":
            let b = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversation.id)/mute", method: .post, body: ["muted": false])
            Task { _ = try? await client.send(b, as: NoContent.self, defaultValue: NoContent()); busy = false }
        case "pin":
            let b = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversation.id)/pin", method: .post, body: ["pinned": true])
            Task { _ = try? await client.send(b, as: NoContent.self, defaultValue: NoContent()); busy = false }
        case "unpin":
            let b = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversation.id)/pin", method: .post, body: ["pinned": false])
            Task { _ = try? await client.send(b, as: NoContent.self, defaultValue: NoContent()); busy = false }
        default:
            let b = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversation.id)", method: .delete)
            Task { _ = try? await client.send(b, as: NoContent.self, defaultValue: NoContent()); busy = false }
        }
    }
}

struct EditMessageSheet: View {
    let message: MessageOut
    let store: ChatMessageStore
    @State private var text: String
    @State private var saving = false
    @Environment(\.dismiss) private var dismiss

    init(message: MessageOut, store: ChatMessageStore) {
        self.message = message
        self.store = store
        _text = State(initialValue: message.body ?? "")
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: Theme.Metrics.padding) {
                TextField("Message", text: $text, axis: .vertical)
                    .lineLimit(2...6)
                    .padding(Theme.Metrics.padding)
                    .background(Theme.Palette.surface)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.Metrics.radiusSmall, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.Metrics.radiusSmall, style: .continuous)
                            .stroke(Theme.Palette.outline, lineWidth: Theme.Metrics.lineWidth)
                    )
                Button {
                    Task {
                        saving = true
                        await store.edit(messageID: message.id, body: text)
                        saving = false
                        dismiss()
                    }
                } label: {
                    Text(saving ? "Saving…" : "Save")
                        .font(.headline)
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .padding(Theme.Metrics.padding)
                        .background(Theme.Palette.brand)
                        .clipShape(RoundedRectangle(cornerRadius: Theme.Metrics.radius, style: .continuous))
                }
                .disabled(text.trimmingCharacters(in: .whitespaces).isEmpty || saving)
                Spacer()
            }
            .padding(Theme.Metrics.padding)
            .background(Theme.Palette.background)
            .navigationTitle("Edit message")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    CloseToolbarButton { dismiss() }
                }
            }
        }
    }
}

struct TalkButton: View {
    let recorder: VoiceRecorder
    @State private var pressed = false

    var body: some View {
        Button {
            // Hold-to-talk begins on press, ends on release.
        } label: {
            Image(systemName: recorder.isRecording ? "waveform.badge.mic" : "mic.fill")
                .font(.system(size: 22))
                .foregroundStyle(Theme.Palette.brand)
                .padding(8)
                .background(Theme.Palette.bubbleIncoming)
                .clipShape(Circle())
        }
        .simultaneousGesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in
                    guard !pressed else { return }
                    pressed = true
                    recorder.start()
                }
                .onEnded { _ in
                    pressed = false
                    recorder.stop()
                }
        )
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
    @State private var player = VoicePlayer()

    var body: some View {
        HStack {
            if isOutgoing { Spacer(minLength: 48) }
            VStack(alignment: isOutgoing ? .trailing : .leading, spacing: 3) {
                if message.isVoice {
                    voiceBubble
                } else if message.isImage, let attachment = message.displayAttachment, let url = URL(string: attachment.url) {
                    AsyncImage(url: url) { phase in
                        switch phase {
                        case .success(let image):
                            image.resizable().scaledToFill()
                        case .failure:
                            Image(systemName: "photo")
                                .foregroundStyle(Theme.Palette.brand)
                        default:
                            ProgressView().tint(Theme.Palette.brand)
                        }
                    }
                    .frame(width: 200, height: 200)
                    .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
                } else {
                    bubbleText
                }
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
                if let reactions = message.reactions, !reactions.isEmpty {
                    HStack(spacing: 4) {
                        ForEach(reactions.sorted(by: { $0.key < $1.key }), id: \.key) { emoji, users in
                            Text("\(emoji) \(users.count)")
                                .font(.caption2)
                                .padding(.horizontal, 6)
                                .padding(.vertical, 2)
                                .background(Theme.Palette.surface)
                                .clipShape(Capsule())
                                .overlay(Capsule().stroke(Theme.Palette.outline, lineWidth: Theme.Metrics.lineWidth))
                        }
                    }
                }
            }
            if !isOutgoing { Spacer(minLength: 48) }
        }
    }

    private var bubbleText: some View {
        Text(message.body ?? "Message deleted")
            .font(Theme.Typography.body)
            .foregroundStyle(isOutgoing ? .white : Theme.Palette.textPrimary)
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
            .background(isOutgoing ? Theme.Palette.bubbleOutgoing : Theme.Palette.bubbleIncoming)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private var voiceBubble: some View {
        HStack(spacing: 8) {
            Button {
                if let url = playerURL {
                    player.toggle(url: url)
                }
            } label: {
                Image(systemName: player.isPlaying ? "stop.fill" : "play.fill")
                    .font(.system(size: 14))
                    .foregroundStyle(isOutgoing ? .white : Theme.Palette.brand)
            }
            Image(systemName: "waveform")
                .font(.system(size: 20))
                .foregroundStyle(isOutgoing ? .white : Theme.Palette.brand)
            Text(voiceDurationLabel)
                .font(.caption)
                .foregroundStyle(isOutgoing ? .white : Theme.Palette.textSecondary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 9)
        .background(isOutgoing ? Theme.Palette.bubbleOutgoing : Theme.Palette.bubbleIncoming)
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private var playerURL: URL? {
        guard let urlString = message.displayAttachment?.url ?? message.mediaUrl else { return nil }
        return URL(string: urlString)
    }

    private var voiceDurationLabel: String {
        guard let ms = message.durationMs else { return "" }
        return String(format: "0:%02d", ms / 1000)
    }

    private var timeLabel: String {
        let formatter = DateFormatter()
        formatter.timeStyle = .short
        return formatter.string(from: message.sentAt)
    }
}