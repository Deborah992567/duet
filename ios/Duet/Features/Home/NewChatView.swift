import SwiftUI

/// Compose a new conversation: pick one friend (direct) or several (group).
struct NewChatView: View {
    @State private var store = FriendsStore()
    @State private var creating = false
    @State private var errorText: String?
    @State private var mode: Mode = .direct
    @State private var selected: Set<String> = []
    @State private var groupName = ""
    @Environment(\.dismiss) private var dismiss
    @Binding var path: NavigationPath

    enum Mode: String, CaseIterable {
        case direct = "Direct"
        case group = "Group"
    }

    var body: some View {
        VStack(spacing: 0) {
            Picker("", selection: $mode) {
                ForEach(Mode.allCases, id: \.self) { m in Text(m.rawValue).tag(m) }
            }
            .pickerStyle(.segmented)
            .padding(Theme.Metrics.padding)

            if mode == .group {
                TextField("Group name", text: $groupName)
                    .padding(Theme.Metrics.padding)
                    .background(Theme.Palette.surface)
                    .clipShape(RoundedRectangle(cornerRadius: Theme.Metrics.radiusSmall, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.Metrics.radiusSmall, style: .continuous)
                            .stroke(Theme.Palette.outline, lineWidth: Theme.Metrics.lineWidth)
                    )
                    .padding(.horizontal, Theme.Metrics.padding)
            }

            List {
                if store.friends.isEmpty {
                    Text("You have no friends yet. Add some in People first.")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.textSecondary)
                }
                ForEach(store.friends) { entry in
                    Button {
                        toggleSelection(entry.user.id)
                    } label: {
                        row(entry.user)
                    }
                    .disabled(creating)
                }
            }
            .scrollContentBackground(.hidden)
            .background(Theme.Palette.background)

            if mode == .group {
                createGroupButton
            }
        }
        .background(Theme.Palette.background)
        .navigationTitle(mode == .direct ? "New message" : "New group")
        .navigationBarTitleDisplayMode(.inline)
        .task { await store.refresh() }
    }

    private func row(_ user: FriendUser) -> some View {
        HStack(spacing: Theme.Metrics.padding) {
            ZStack {
                Circle().fill(Theme.Palette.bubbleIncoming).frame(width: 42, height: 42)
                Text(String(user.name.prefix(1)).uppercased())
                    .font(.headline)
                    .foregroundStyle(Theme.Palette.brand)
            }
            Text(user.name)
                .font(Theme.Typography.body)
                .foregroundStyle(Theme.Palette.textPrimary)
            Spacer()
            if mode == .group {
                Image(systemName: selected.contains(user.id) ? "checkmark.circle.fill" : "circle")
                    .foregroundStyle(selected.contains(user.id) ? Theme.Palette.brand : Theme.Palette.textSecondary)
            } else if creating {
                ProgressView().tint(Theme.Palette.brand)
            }
        }
    }

    private var createGroupButton: some View {
        Button {
            createGroup()
        } label: {
            Text(creating ? "Creating…" : "Create group")
                .font(.headline)
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .padding(Theme.Metrics.padding)
                .background(Theme.Palette.brand)
                .clipShape(RoundedRectangle(cornerRadius: Theme.Metrics.radius, style: .continuous))
                .padding(Theme.Metrics.padding)
        }
        .disabled(creating || selected.isEmpty || groupName.trimmingCharacters(in: .whitespaces).isEmpty)
    }

    private func toggleSelection(_ id: String) {
        guard mode == .group else {
            startDirect(with: id)
            return
        }
        if selected.contains(id) { selected.remove(id) } else { selected.insert(id) }
    }

    private func startDirect(with friendID: String) {
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
                path.append(summary(from: detail))
            } catch {
                creating = false
                errorText = (error as? APIError)?.message ?? "Could not start chat."
            }
        }
    }

    private func createGroup() {
        creating = true
        Task {
            do {
                let client = APIClient.shared
                let builder = URLRequestBuilder(
                    base: client.baseURL,
                    path: "/v1/conversations/groups",
                    method: .post,
                    body: CreateGroupBody(name: groupName, member_ids: Array(selected))
                )
                let detail: ConversationDetail = try await client.send(builder, as: ConversationDetail.self)
                creating = false
                dismiss()
                path.append(summary(from: detail))
            } catch {
                creating = false
                errorText = (error as? APIError)?.message ?? "Could not create group."
            }
        }
    }

    private func summary(from detail: ConversationDetail) -> ConversationSummary {
        ConversationSummary(
            id: detail.id,
            type: "group",
            name: detail.name,
            lastMessagePreview: nil,
            lastMessageAt: nil,
            unreadCount: 0,
            isPinned: false,
            isMuted: false,
            memberCount: detail.memberCount,
            peer: nil,
            currentStreak: 0,
            streakAlive: false
        )
    }
}

struct CreateGroupBody: Encodable {
    let name: String
    let member_ids: [String]
}

struct ConversationDetail: Decodable {
    let id: String
    let type: String
    let name: String?
    let memberCount: Int
    let peer: UserPublic?

    enum CodingKeys: String, CodingKey {
        case id, type, name, peer
        case memberCount = "member_count"
    }
}