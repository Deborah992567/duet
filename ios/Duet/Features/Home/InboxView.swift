import SwiftUI

/// Inbox: list of conversations.
struct InboxView: View {
    @Environment(AppState.self) private var state
    @State private var store = ConversationListStore()
    @State private var typing = TypingStore()
    @State private var presence = PresenceStore()
    @State private var showFriends = false
    @State private var showNewChat = false
    @State private var showNotifications = false
    @State private var showOnboarding = false
    @State private var path = NavigationPath()

    var body: some View {
        NavigationStack(path: $path) {
            ScrollView {
                LazyVStack(spacing: Theme.Metrics.small) {
                    if store.conversations.isEmpty {
                        emptyState
                    } else {
                        ForEach(store.conversations) { conversation in
                            NavigationLink(value: conversation) {
                                InboxRow(
                                    conversation: conversation,
                                    isTyping: typing.isTyping(in: conversation.id),
                                    isOnline: presence.isOnline(userID: conversation.peer?.id)
                                )
                                .padding(.horizontal, Theme.Metrics.padding)
                            }
                            .buttonStyle(.plain)
                            .contextMenu {
                                Button {
                                    Task {
                                        await applyAction(conversation.isMuted ? "unmute" : "mute", on: conversation)
                                        await store.refresh()
                                    }
                                } label: {
                                    Label(conversation.isMuted ? "Unmute" : "Mute", systemImage: conversation.isMuted ? "bell.fill" : "bell.slash")
                                }
                                Button {
                                    Task {
                                        await applyAction(conversation.isPinned ? "unpin" : "pin", on: conversation)
                                        await store.refresh()
                                    }
                                } label: {
                                    Label(conversation.isPinned ? "Unpin" : "Pin", systemImage: conversation.isPinned ? "pin.slash" : "pin")
                                }
                                Divider()
                                Button(role: .destructive) {
                                    Task {
                                        await applyAction("hide", on: conversation)
                                        await store.refresh()
                                    }
                                } label: {
                                    Label("Hide conversation", systemImage: "trash")
                                }
                            }
                        }
                    }
                }
                .padding(.vertical, Theme.Metrics.small)
                .navigationDestination(for: ConversationSummary.self) { conversation in
                    ChatView(conversation: conversation)
                }
                .navigationDestination(isPresented: $showFriends) {
                    FriendsView()
                }
            }
            .background(Theme.Palette.background)
            .navigationTitle("Inbox")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        showFriends = true
                    } label: {
                        Image(systemName: "person.2.fill")
                            .foregroundStyle(Theme.Palette.brand)
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    HStack(spacing: Theme.Metrics.small) {
                        Button {
                            showNotifications = true
                        } label: {
                            Image(systemName: "bell.fill")
                                .foregroundStyle(Theme.Palette.brand)
                        }
                        Button {
                            showNewChat = true
                        } label: {
                            Image(systemName: "square.and.pencil")
                                .foregroundStyle(Theme.Palette.brand)
                        }
                    }
                }
            }
            .refreshable {
                await store.refresh()
            }
            .onOpenURL { url in
                handleDeepLink(url)
            }
            .task {
                typing.start()
                presence.start()
                await store.refresh()
                let ids = store.conversations.map(\.id)
                typing.subscribe(conversationIDs: ids)
                presence.subscribe(conversationIDs: ids)
                if !UserDefaults.standard.bool(forKey: "onboarding.done") {
                    showOnboarding = true
                }
            }
        }
        .onDisappear {
            typing.stop()
            presence.stop()
        }
        .sheet(isPresented: $showNewChat) {
            NavigationStack {
                NewChatView(path: $path)
                    .toolbar {
                        ToolbarItem(placement: .topBarTrailing) {
                            CloseToolbarButton { showNewChat = false }
                        }
                    }
            }
        }
        .sheet(isPresented: $showNotifications) {
            NotificationsFeedView()
        }
        .sheet(isPresented: $showOnboarding) {
            OnboardingSheet {
                showOnboarding = false
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: Theme.Metrics.small) {
            Image(systemName: "bubble.left.and.bubble.right")
                .font(.system(size: 48))
                .foregroundStyle(Theme.Palette.textSecondary)
            Text("No conversations yet")
                .font(Theme.Typography.headline)
                .foregroundStyle(Theme.Palette.textPrimary)
            Text("Send your first message to start a streak.")
                .font(Theme.Typography.body)
                .foregroundStyle(Theme.Palette.textSecondary)
            Button {
                showNewChat = true
            } label: {
                Label("Start a conversation", systemImage: "square.and.pencil")
                    .font(Theme.Typography.body.bold())
                    .foregroundStyle(.white)
                    .padding(.horizontal, Theme.Metrics.padding)
                    .padding(.vertical, 10)
                    .background(Theme.Palette.brand)
                    .clipShape(Capsule())
            }
            .padding(.top, Theme.Metrics.small)
        }
        .padding(Theme.Metrics.padding)
        .cardStyle()
        .padding(.top, Theme.Metrics.padding * 4)
    }

    private func applyAction(_ action: String, on conversation: ConversationSummary) async {
        let client = APIClient.shared
        let builder: URLRequestBuilder
        switch action {
        case "mute":
            builder = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversation.id)/mute", method: .post, body: ["muted": true])
        case "unmute":
            builder = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversation.id)/mute", method: .post, body: ["muted": false])
        case "pin":
            builder = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversation.id)/pin", method: .post, body: ["pinned": true])
        case "unpin":
            builder = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversation.id)/pin", method: .post, body: ["pinned": false])
        default:
            builder = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations/\(conversation.id)", method: .delete)
        }
        _ = try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())
    }

    private func handleDeepLink(_ url: URL) {
        guard url.scheme == "duet" else { return }
        switch url.host {
        case "inbox":
            return
        default:
            let conversationID = url.host ?? url.pathComponents.last
            guard let conversationID else { return }
            Task {
                await store.refresh()
                if let conversation = store.conversations.first(where: { $0.id == conversationID }) {
                    path.append(conversation)
                }
            }
        }
    }
}