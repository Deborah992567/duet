import SwiftUI

/// Inbox: list of conversations.
struct InboxView: View {
    @Environment(AppState.self) private var state
    @State private var store = ConversationListStore()

    var body: some View {
        NavigationStack {
            ScrollView {
                LazyVStack(spacing: Theme.Metrics.small) {
                    if store.conversations.isEmpty {
                        emptyState
                    } else {
                        ForEach(store.conversations) { conversation in
                            NavigationLink(value: conversation) {
                                InboxRow(conversation: conversation)
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
            }
            .background(Theme.Palette.background)
            .navigationTitle("Inbox")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        // Friends list
                    } label: {
                        Image(systemName: "person.2.fill")
                            .foregroundStyle(Theme.Palette.brand)
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        // New message
                    } label: {
                        Image(systemName: "square.and.pencil")
                            .foregroundStyle(Theme.Palette.brand)
                    }
                }
            }
            .refreshable {
                await store.refresh()
            }
            .task {
                await store.refresh()
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
        }
        .padding(Theme.Metrics.padding)
        .cardStyle()
        .padding(.top, Theme.Metrics.padding * 4)
    }
}