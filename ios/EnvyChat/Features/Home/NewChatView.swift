import SwiftUI

/// Compose a new direct conversation: choose a friend, then create the conversation server-side.
struct NewChatView: View {
    @State private var store = FriendsStore()
    @State private var creating = false
    @State private var errorText: String?
    @Environment(\.dismiss) private var dismiss
    @Binding var path: NavigationPath

    var body: some View {
        List {
            if store.friends.isEmpty {
                Text("You have no friends yet. Add some in People first.")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.textSecondary)
            }
            ForEach(store.friends) { entry in
                Button {
                    startChat(with: entry.user.id)
                } label: {
                    HStack(spacing: Theme.Metrics.padding) {
                        ZStack {
                            Circle().fill(Theme.Palette.bubbleIncoming).frame(width: 42, height: 42)
                            Text(String(entry.user.name.prefix(1)).uppercased())
                                .font(.headline)
                                .foregroundStyle(Theme.Palette.brand)
                        }
                        Text(entry.user.name)
                            .font(Theme.Typography.body)
                            .foregroundStyle(Theme.Palette.textPrimary)
                        Spacer()
                        if creating { ProgressView().tint(Theme.Palette.brand) }
                    }
                }
                .disabled(creating)
            }
        }
        .background(Theme.Palette.background)
        .scrollContentBackground(.hidden)
        .navigationTitle("New message")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.refresh() }
    }

    private func startChat(with friendID: String) {
        creating = true
        Task {
            do {
                let client = APIClient.shared
                let builder = URLRequestBuilder(
                    base: client.baseURL,
                    path: "/v1/conversations",
                    method: .post,
                    body: ["user_id": friendID]
                )
                let detail: ConversationDetail = try await client.send(builder, as: ConversationDetail.self)
                creating = false
                dismiss()
                path.append(
                    ConversationSummary(
                        id: detail.id,
                        type: "direct",
                        name: detail.name,
                        lastMessagePreview: nil,
                        lastMessageAt: nil,
                        unreadCount: 0,
                        isPinned: false,
                        isMuted: false,
                        memberCount: detail.memberCount,
                        peer: detail.peer,
                        currentStreak: detail.currentStreak ?? 0,
                        streakAlive: detail.streakAlive ?? false
                    )
                )
            } catch {
                creating = false
                errorText = (error as? APIError)?.message ?? "Could not start chat."
            }
        }
    }
}

struct ConversationDetail: Decodable {
    let id: String
    let type: String
    let name: String?
    let memberCount: Int
    let peer: UserPublic?
    let currentStreak: Int?
    let streakAlive: Bool?

    enum CodingKeys: String, CodingKey {
        case id, type, name, peer
        case memberCount = "member_count"
        case currentStreak = "current_streak"
        case streakAlive = "streak_alive"
    }
}