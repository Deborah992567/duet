import Foundation

/// Owns the client's session (tokens + current user). Tokens live in the Keychain.
@Observable
final class SessionStore {
    static let shared = SessionStore()

    var accessToken: String? {
        didSet { persist() }
    }
    var refreshToken: String?
    var currentUserID: String?
    var isSignedIn: Bool { accessToken != nil }

    private let keychain = KeychainStore.shared

    init() {
        accessToken = keychain.string(for: "access_token")
        refreshToken = keychain.string(for: "refresh_token")
        currentUserID = keychain.string(for: "user_id")
    }

    func save(access: String, refresh: String, userID: String) {
        accessToken = access
        refreshToken = refresh
        currentUserID = userID
    }

    func clear() {
        accessToken = nil
        refreshToken = nil
        currentUserID = nil
        keychain.delete(for: "access_token")
        keychain.delete(for: "refresh_token")
        keychain.delete(for: "user_id")
    }

    private func persist() {
        if let accessToken { try? keychain.set(accessToken, for: "access_token") }
        if let refreshToken { try? keychain.set(refreshToken, for: "refresh_token") }
        if let currentUserID { try? keychain.set(currentUserID, for: "user_id") }
    }
}