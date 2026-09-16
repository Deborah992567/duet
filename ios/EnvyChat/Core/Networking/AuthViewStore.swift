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

    func register(email: String, username: String, displayName: String, password: String) async throws {
        struct RegisterRequest: Encodable { let email, username, password, displayName: String }
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/auth/register",
            method: .post,
            body: RegisterRequest(email: email, username: username, password: password, displayName: displayName)
        )
        let response: AuthResponse = try await client.send(builder, as: AuthResponse.self)
        session.save(
            access: response.tokens.accessToken,
            refresh: response.tokens.refreshToken,
            userID: response.user.id
        )
    }

    func requestPasswordReset(email: String) async throws {
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/auth/request-password-reset",
            method: .post,
            body: ["email": email]
        )
        _ = try await client.send(builder, as: NoContent.self, defaultValue: NoContent())
    }

    func resetPassword(token: String, password: String) async throws {
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/auth/reset-password",
            method: .post,
            body: ["reset_token": token, "password": password]
        )
        _ = try await client.send(builder, as: NoContent.self, defaultValue: NoContent())
    }
}

struct NoContent: Decodable {}