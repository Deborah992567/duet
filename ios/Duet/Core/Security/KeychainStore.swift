import Foundation
import Security

enum KeychainError: Error {
    case unexpectedData
    case unhandledError(status: OSStatus)
}

/// Minimal Keychain wrapper for token storage.
final class KeychainStore {
    static let shared = KeychainStore()
    private let service = "com.duet.app"

    private func baseQuery(_ key: String) -> [String: Any] {
        [kSecClass as String: kSecClassGenericPassword,
         kSecAttrService as String: service,
         kSecAttrAccount as String: key]
    }

    func set(_ value: String, for key: String) throws {
        let data = Data(value.utf8)
        var query = baseQuery(key)
        let attrs: [String: Any] = [kSecValueData as String: data]
        let status = SecItemUpdate(query as CFDictionary, attrs as CFDictionary)
        if status == errSecItemNotFound {
            query[kSecValueData as String] = data
            let add = SecItemAdd(query as CFDictionary, nil)
            guard add == errSecSuccess else {
                throw KeychainError.unhandledError(status: add)
            }
        } else if status != errSecSuccess {
            throw KeychainError.unhandledError(status: status)
        }
    }

    func string(for key: String) -> String? {
        var query = baseQuery(key)
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    func delete(for key: String) {
        SecItemDelete(baseQuery(key) as CFDictionary)
    }
}