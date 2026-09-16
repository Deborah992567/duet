import Foundation

struct AuthTokens: Decodable {
    let accessToken: String
    let refreshToken: String
    let expiresIn: Int

    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case expiresIn = "expires_in"
    }
}

struct AuthResponse: Decodable {
    let tokens: AuthTokens
    let user: UserPublic
    let registered: Bool
}

struct UserPublic: Decodable, Identifiable, Hashable {
    let id: String
    let username: String
    let displayName: String?
    let avatarUrl: String?
    let isOnline: Bool?

    enum CodingKeys: String, CodingKey {
        case id, username
        case displayName = "display_name"
        case avatarUrl = "avatar_url"
        case isOnline = "is_online"
    }
}

/// Auth feature store. Backs the login/register/reset flows.
@Observable
final class AuthViewStore {
    static let shared = AuthViewStore()
    private let session = SessionStore.shared
    private let client = APIClient.shared

    func signIn(identifier: String, password: String) async throws {
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/auth/login",
            method: .post,
            body: ["identifier": identifier, "password": password]
        )
        let response: AuthResponse = try await client.send(builder, as: AuthResponse.self)
        session.save(
            access: response.tokens.accessToken,
            refresh: response.tokens.refreshToken,
            userID: response.user.id
        )
    }
}