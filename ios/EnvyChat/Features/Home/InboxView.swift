import SwiftUI

/// Inbox: list of conversations.
struct InboxView: View {
    @Environment(AppState.self) private var state
    @State private var store = ConversationListStore()
    @State private var typing = TypingStore()
    @State private var showFriends = false
    @State private var showNewChat = false
    @State private var showNotifications = false
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
                                    isTyping: typing.isTyping(in: conversation.id)
                                )
                                .padding(.horizontal, Theme.Metrics.padding)
                            }
                            .buttonStyle(.plain)
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
            .task {
                typing.start()
                await store.refresh()
                typing.subscribe(conversationIDs: store.conversations.map(\.id))
            }
        }
        .onDisappear { typing.stop() }
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
        }
        .padding(Theme.Metrics.padding)
        .cardStyle()
        .padding(.top, Theme.Metrics.padding * 4)
    }
}