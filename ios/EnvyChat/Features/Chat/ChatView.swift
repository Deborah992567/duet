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
    @State private var replyingTo: MessageOut?
    @State private var forwardMessage: MessageOut?
    @State private var showProfile = false
    @State private var showSearch = false
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
        .navigationTitle(navigationTitleText)
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { toolbarItems }
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
        .sheet(item: $forwardMessage) { ForwardSheet(message: $0) }
        .sheet(isPresented: $showProfile) {
            if let peer = conversation.peer {
                UserProfileSheet(userID: peer.id)
            }
        }
        .sheet(isPresented: $showSearch) {
            SearchMessagesView(conversationID: conversation.id)
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
                            isOutgoing: message.senderId == SessionStore.shared.currentUserID,
                            quote: store.messages.first(where: { $0.id == message.replyToMessageId })?.body
                        )
                        .contextMenu {
                            MessageActionsMenu(message: message, store: store, onReply: {
                                replyingTo = message
                            }, onEdit: {
                                editingMessage = message
                            }, onForward: {
                                forwardMessage = message
                            })
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
        VStack(spacing: 0) {
            if let replyingTo {
                HStack(spacing: 8) {
                    Image(systemName: "arrowshape.turn.up.left.fill")
                        .font(.caption2)
                        .foregroundStyle(Theme.Palette.brand)
                    Text("Reply to “\(replyingTo.body ?? "voice message")”")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.textPrimary)
                        .lineLimit(1)
                    Spacer()
                    Button { self.replyingTo = nil } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(Theme.Palette.textSecondary)
                    }
                }
                .padding(.horizontal, Theme.Metrics.padding)
                .padding(.vertical, 6)
                .background(Theme.Palette.bubbleIncoming)
            }

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
        }
        .padding(Theme.Metrics.padding)
        .background(Theme.Palette.surface)
        .overlay(alignment: .top) {
            Rectangle().fill(Theme.Palette.outline).frame(height: Theme.Metrics.lineWidth)
        }
    }

    private var navigationTitleText: String {
        conversation.name ?? conversation.peer?.username ?? "Chat"
    }

    @ToolbarContentBuilder
    private var toolbarItems: some ToolbarContent {
        ToolbarItem(placement: .topBarLeading) {
            PresenceButton(peerOnline: peerOnline, peerType: conversation.type, peerID: conversation.peer?.id) {
                showProfile = true
            }
        }
        ToolbarItem(placement: .topBarTrailing) {
            Menu {
                Button {
                    showSearch = true
                } label: {
                    Label("Search messages", systemImage: "magnifyingglass")
                }
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

    private func send() {
        let body = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty else { return }
        let clientID = UUID().uuidString.lowercased()
        let replyID = replyingTo?.id
        draft = ""
        replyingTo = nil
        Task {
            let didSend = await store.send(body: body, clientID: clientID, replyTo: replyID)
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

struct PresenceButton: View {
    let peerOnline: Bool
    let peerType: String
    let peerID: String?
    var onTap: () -> Void

    var body: some View {
        if peerType == "direct", peerID != nil {
            Button(action: onTap) {
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
    }
}

struct MessageActionsMenu: View {
    let message: MessageOut
    let store: ChatMessageStore
    var onReply: (() -> Void)?
    var onEdit: (() -> Void)?
    var onForward: (() -> Void)?

    var body: some View {
        Button(action: { onReply?() }) {
            Label("Reply", systemImage: "arrowshape.turn.up.left.fill")
        }
        Button(action: { onForward?() }) {
            Label("Forward", systemImage: "arrowshape.turn.up.right.fill")
        }
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
    var quote: String?
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
        VStack(alignment: isOutgoing ? .trailing : .leading, spacing: 4) {
            if let quote, !quote.isEmpty {
                HStack(spacing: 4) {
                    Rectangle()
                        .fill(Theme.Palette.brand.opacity(0.5))
                        .frame(width: 3)
                    Text(quote)
                        .font(.caption2)
                        .foregroundStyle(isOutgoing ? .white.opacity(0.7) : Theme.Palette.textSecondary)
                        .lineLimit(2)
                }
                .padding(4)
                .background(isOutgoing ? Color.white.opacity(0.15) : Theme.Palette.bubbleIncoming.opacity(0.6))
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
            Text(message.body ?? "Message deleted")
                .font(Theme.Typography.body)
                .foregroundStyle(isOutgoing ? .white : Theme.Palette.textPrimary)
        }
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

struct UserProfileSheet: View {
    let userID: String
    @State private var user: UserPublic?
    @State private var isLoading = true
    @State private var friendRequestSent = false
    @State private var blocked = false
    @State private var showBlockConfirm = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if isLoading {
                    ProgressView()
                } else if let user {
                    VStack(spacing: Theme.Metrics.padding) {
                        avatar(for: user)
                        let name = user.displayName?.isEmpty == false ? user.displayName ?? user.username : user.username
                        Text(name)
                            .font(Theme.Typography.title)
                            .foregroundStyle(Theme.Palette.textPrimary)
                        Text("@\(user.username)")
                            .font(Theme.Typography.caption)
                            .foregroundStyle(Theme.Palette.textSecondary)
                        if !(user.bio ?? "").isEmpty {
                            Text(user.bio ?? "")
                                .font(Theme.Typography.body)
                                .foregroundStyle(Theme.Palette.textPrimary)
                                .multilineTextAlignment(.center)
                        }
                        let isOnline = user.online ?? false
                        HStack(spacing: Theme.Metrics.small) {
                            Circle()
                                .fill(isOnline ? Theme.Palette.success : Theme.Palette.flameOff)
                                .frame(width: 9, height: 9)
                            Text(isOnline ? "Online" : "Last seen \(user.lastSeenAt?.relativeFormatted ?? "recently")")
                                .font(Theme.Typography.caption)
                                .foregroundStyle(Theme.Palette.textSecondary)
                        }
                        if user.isFriend {
                            Label("Friends on Envy", systemImage: "person.2.fill")
                                .font(Theme.Typography.caption)
                                .foregroundStyle(Theme.Palette.brand)
                        } else if !user.isBlocked {
                            Button {
                                friendRequestSent = true
                                Task { await sendFriendRequest(to: user.id) }
                            } label: {
                                Text(friendRequestSent ? "Request sent" : "Add Friend")
                                    .font(Theme.Typography.body.bold())
                                    .foregroundStyle(friendRequestSent ? Theme.Palette.textSecondary : .white)
                                    .padding(.horizontal, Theme.Metrics.padding)
                                    .padding(.vertical, 10)
                                    .background(friendRequestSent ? Color.gray : Theme.Palette.brand)
                                    .clipShape(Capsule())
                            }
                            .disabled(friendRequestSent)
                        }
                        Button(role: .destructive) {
                            showBlockConfirm = true
                        } label: {
                            Label(blocked ? "Unblock user" : "Block user", systemImage: "hand.raised.fill")
                                .font(Theme.Typography.caption)
                                .foregroundStyle(Theme.Palette.danger)
                                .padding(8)
                        }
                        .confirmationDialog(blocked ? "Unblock \(user.username)?" : "Block \(user.username)? You won't see their messages.", isPresented: $showBlockConfirm, titleVisibility: .visible) {
                            Button(blocked ? "Unblock" : "Block", role: .destructive) {
                                blocked.toggle()
                                Task { await setBlocked(blocked) }
                            }
                        }
                        Spacer()
                    }
                    .padding(Theme.Metrics.padding)
                } else {
                    ContentUnavailableView("User unavailable", systemImage: "person.crop.circle.badge.questionmark")
                }
            }
            .navigationTitle("Profile")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
            .task {
                await load()
            }
        }
    }

    private func avatar(for user: UserPublic) -> some View {
        AsyncImage(url: user.avatarUrl.flatMap(URL.init(string:))) { phase in
            switch phase {
            case .success(let image):
                image.resizable().scaledToFill()
            default:
                Image(systemName: "person.crop.circle.fill")
                    .resizable()
                    .foregroundStyle(Theme.Palette.brand.opacity(0.7))
            }
        }
        .frame(width: 96, height: 96)
        .clipShape(Circle())
    }

    private func load() async {
        let client = APIClient.shared
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/users/\(userID)")
        if let fetched = try? await client.send(builder, as: UserPublic.self) {
            user = fetched
            blocked = fetched.isBlocked
        }
        isLoading = false
    }

    private func sendFriendRequest(to userID: String) async {
        let client = APIClient.shared
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/friends/requests", method: .post, body: ["user_id": userID])
        _ = try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())
    }

    private func setBlocked(_ blocked: Bool) async {
        let client = APIClient.shared
        let path = "/v1/users/\(userID)/block"
        let builder = URLRequestBuilder(base: client.baseURL, path: path, method: blocked ? .post : .delete)
        _ = try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())
    }
}

struct SearchMessagesView: View {
    let conversationID: String
    @State private var query = ""
    @State private var results: [MessageOut] = []
    @State private var searched = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                HStack(spacing: Theme.Metrics.small) {
                    Image(systemName: "magnifyingglass")
                        .foregroundStyle(Theme.Palette.textSecondary)
                    TextField("Search this chat", text: $query)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled(true)
                        .submitLabel(.search)
                        .onSubmit { Task { await search() } }
                    if !query.isEmpty {
                        Button { query = ""; results = []; searched = false } label: {
                            Image(systemName: "xmark.circle.fill")
                                .foregroundStyle(Theme.Palette.textSecondary)
                        }
                    }
                }
                .padding(Theme.Metrics.padding)
                .background(Theme.Palette.surface)

                List {
                    if searched && results.isEmpty {
                        ContentUnavailableView("No matches", systemImage: "magnifyingglass", description: Text("Try a different word."))
                    } else {
                        ForEach(results) { message in
                            VStack(alignment: .leading, spacing: 4) {
                                Text(message.body ?? "Voice or image message")
                                    .font(Theme.Typography.body)
                                    .foregroundStyle(Theme.Palette.textPrimary)
                                    .lineLimit(2)
                                Text(message.sentAt.relativeFormatted)
                                    .font(Theme.Typography.caption)
                                    .foregroundStyle(Theme.Palette.textSecondary)
                            }
                            .padding(.vertical, 4)
                        }
                    }
                }
                .listStyle(.plain)
            }
            .navigationTitle("Search")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }

    private func search() async {
        let trimmed = query.trimmingCharacters(in: .whitespaces)
        guard !trimmed.isEmpty else { return }
        let client = APIClient.shared
        let body = SearchMessagesBody(query: trimmed, conversation_id: conversationID, limit: 50)
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/messages/search", method: .post, body: body)
        if let response: MessageListResponse = try? await client.send(builder, as: MessageListResponse.self) {
            results = response.items
        }
        searched = true
    }
}

struct SearchMessagesBody: Encodable {
    let query: String
    let conversation_id: String
    let limit: Int
}

struct ForwardSheet: View {
    let message: MessageOut
    @Environment(\.dismiss) private var dismiss
    @State private var list = ConversationListStore()
    @AppStorage("forwardingCount") private var forwardingCount = 0

    var body: some View {
        NavigationStack {
            Group {
                if list.isLoading && list.conversations.isEmpty {
                    ProgressView()
                } else {
                    List(list.conversations) { conversation in
                        Button {
                            Task {
                                let store = ChatMessageStore(conversationID: conversation.id, local: nil)
                                let forwarded = "[Forwarded] \(message.body ?? "voice message")"
                                if await store.send(body: forwarded, clientID: UUID().uuidString.lowercased()) {
                                    forwardingCount += 1
                                }
                                dismiss()
                            }
                        } label: {
                            HStack(spacing: Theme.Metrics.small) {
                                Image(systemName: conversation.type == "group" ? "person.3.fill" : "person.crop.circle.fill")
                                    .foregroundStyle(Theme.Palette.brand)
                                Text(conversation.name ?? "Conversation")
                                    .foregroundStyle(Theme.Palette.textPrimary)
                                Spacer()
                                Image(systemName: "paperplane.fill")
                                    .font(.caption)
                                    .foregroundStyle(Theme.Palette.textSecondary)
                            }
                        }
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("Forward to…")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                }
            }
            .task { await list.refresh() }
        }
        .presentationDetents([.medium, .large])
    }
}