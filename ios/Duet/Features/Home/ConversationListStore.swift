import Foundation
import Observation

@Observable
final class ConversationListStore {
    private(set) var conversations: [ConversationSummary] = []
    private(set) var isLoading = false
    var errorText: String?

    private let client = APIClient.shared

    func refresh() async {
        isLoading = true
        defer { isLoading = false }
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/conversations")
        do {
            let resp: ConversationListResponse = try await client.send(builder, as: ConversationListResponse.self)
            conversations = resp.items.sorted { lhs, rhs in
                if lhs.isPinned != rhs.isPinned { return lhs.isPinned }
                return (lhs.lastMessageAt ?? .distantPast) > (rhs.lastMessageAt ?? .distantPast)
            }
        } catch {
            errorText = (error as? APIError)?.message ?? "Could not load conversations."
        }
    }
}