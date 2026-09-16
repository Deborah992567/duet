import Foundation
import Observation

struct FriendUser: Decodable, Identifiable, Hashable {
    let id: String
    let username: String
    let displayName: String?
    let isOnline: Bool?

    enum CodingKeys: String, CodingKey {
        case id, username
        case displayName = "display_name"
        case isOnline = "is_online"
    }

    var name: String { displayName ?? username }
}

struct FriendEntry: Decodable, Identifiable, Hashable {
    let id: String
    let user: FriendUser
    let since: Date?
}

struct FriendsListResponse: Decodable {
    let items: [FriendEntry]
    let hasMore: Bool

    enum CodingKeys: String, CodingKey {
        case items
        case hasMore = "has_more"
    }
}

@Observable
final class FriendsStore {
    private(set) var friends: [FriendEntry] = []
    private(set) var incomingRequests: [FriendRequest] = []
    private(set) var searchResults: [FriendUser] = []
    var errorText: String?

    private let client = APIClient.shared

    func refresh() async {
        async let f = load("/v1/friends", as: FriendsListResponse.self)
        async let r = load("/v1/friends/requests/incoming", as: [FriendRequest].self)
        do {
            let (fList, requests) = try await (f, r)
            friends = fList?.items ?? []
            incomingRequests = requests ?? []
        } catch {
            errorText = (error as? APIError)?.message ?? "Could not load friends."
        }
    }

    func search(_ query: String) async {
        guard !query.isEmpty else { searchResults = []; return }
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/users/search", query: [URLQueryItem(name: "q", value: query)])
        searchResults = (try? await client.send(builder, as: SearchResponse.self))?.items ?? []
    }

    func sendRequest(to userID: String) async {
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/friends/requests", method: .post, body: ["user_id": userID])
        _ = try? await client.send(builder, as: RequestResponse.self, defaultValue: nil)
        _ = builder
    }

    func respond(requestID: String, accept: Bool) async {
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/friends/requests/\(requestID)/respond",
            method: .post,
            body: ["accept": accept]
        )
        _ = try? await client.send(builder, as: NoContent.self, defaultValue: NoContent())
        await refresh()
    }

    private func load<T: Decodable>(_ path: String, as type: T.Type) async throws -> T? {
        let builder = URLRequestBuilder(base: client.baseURL, path: path)
        return try await client.send(builder, as: type, defaultValue: nil)
    }
}

struct SearchResponse: Decodable {
    let items: [FriendUser]
}

struct RequestResponse: Decodable {
    let request_id: String
    let reverse: Bool?
}

struct FriendRequest: Decodable, Identifiable, Hashable {
    let id: String
    let sender: FriendUser
    let message: String?
    let sent_at: Date?
}