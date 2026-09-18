import SwiftUI
import Observation

struct NotificationItem: Decodable, Identifiable, Hashable {
    let id: Int
    let kind: String
    let title: String
    let body: String?
    let readAt: Date?
    let createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, kind, title, body
        case readAt = "read_at"
        case createdAt = "created_at"
    }
}

struct NotificationListResponse: Decodable {
    let items: [NotificationItem]
}

@Observable
final class NotificationStore {
    private(set) var items: [NotificationItem] = []
    private(set) var isLoading = false

    private let client = APIClient.shared

    func refresh() async {
        isLoading = true
        defer { isLoading = false }
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/notifications")
        items = (try? await client.send(builder, as: NotificationListResponse.self, defaultValue: nil))?.items ?? []
    }

    func markRead(_ item: NotificationItem) async {
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/notifications/\(item.id)/read", method: .post)
        _ = try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())
        if let index = items.firstIndex(where: { $0.id == item.id }) {
            items[index] = NotificationItem(id: item.id, kind: item.kind, title: item.title, body: item.body, readAt: Date(), createdAt: item.createdAt)
        }
    }

    func markAllRead() async {
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/notifications/read-all", method: .post)
        _ = try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())
        await refresh()
    }
}

struct NotificationsFeedView: View {
    @State private var store = NotificationStore()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            Group {
                if store.items.isEmpty {
                    if store.isLoading {
                        ProgressView()
                    } else {
                        ContentUnavailableView("No notifications", systemImage: "bell.slash", description: Text("Milestones, friend requests and reminders will land here."))
                    }
                } else {
                    List {
                        ForEach(store.items) { item in
                            HStack(alignment: .top, spacing: Theme.Metrics.small) {
                                Image(systemName: icon(for: item.kind))
                                    .foregroundStyle(Theme.Palette.brand)
                                    .frame(width: 28)
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(item.title)
                                        .font(Theme.Typography.body.bold())
                                        .foregroundStyle(Theme.Palette.textPrimary)
                                    if let body = item.body {
                                        Text(body)
                                            .font(Theme.Typography.caption)
                                            .foregroundStyle(Theme.Palette.textSecondary)
                                    }
                                    if let createdAt = item.createdAt {
                                        Text(createdAt.relativeFormatted)
                                            .font(.caption2)
                                            .foregroundStyle(Theme.Palette.textSecondary)
                                    }
                                }
                                Spacer()
                                if item.readAt == nil {
                                    Circle()
                                        .fill(Theme.Palette.brand)
                                        .frame(width: 8, height: 8)
                                }
                            }
                            .padding(.vertical, 2)
                            .contentShape(Rectangle())
                            .onTapGesture {
                                Task { await store.markRead(item) }
                            }
                        }
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("Notifications")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Done") { dismiss() }
                }
                ToolbarItem(placement: .topBarLeading) {
                    Button("Mark all read") { Task { await store.markAllRead() } }
                        .disabled(store.items.allSatisfy { $0.readAt != nil })
                }
            }
            .task { await store.refresh() }
        }
        .presentationDetents([.medium, .large])
    }

    private func icon(for kind: String) -> String {
        switch kind {
        case "streak_milestone": return "flame.fill"
        case "streak_break": return "flame.slash"
        case "friend_request": return "person.fill.badge.plus"
        case "call": return "phone.fill"
        case "security": return "shield.fill"
        default: return "bell.fill"
        }
    }
}