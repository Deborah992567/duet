import Foundation

struct APIError: Error, Decodable {
    let code: String
    let message: String
    let retryable: Bool
    let details: [String: String]?

    var errorDescription: String { message }

    static func unknown(_ message: String = "Something went wrong.") -> APIError {
        APIError(code: "unknown", message: message, retryable: false, details: nil)
    }
}

enum HTTPMethod: String {
    case get = "GET"
    case post = "POST"
    case patch = "PATCH"
    case delete = "DELETE"
}

struct URLRequestBuilder {
    let base: String
    let path: String
    var method: HTTPMethod = .get
    var query: [URLQueryItem] = []
    var body: Encodable?
    var token: String?

    func build() throws -> URLRequest {
        guard var components = URLComponents(string: base + path) else {
            throw APIError.unknown("Invalid URL.")
        }
        if !query.isEmpty {
            components.queryItems = query
        }
        var request = URLRequest(url: components.url!)
        request.httpMethod = method.rawValue
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            request.httpBody = try JSONEncoder.api.encode(body)
        }
        return request
    }
}

final class APIClient {
    static let shared = APIClient()

    var baseURL: String {
        // Override in Debug via ProcessInfo, default to local dev server.
        ProcessInfo.processInfo.environment["API_BASE_URL"] ?? "http://127.0.0.1:8000"
    }

    func send<Response: Decodable>(
        _ builder: URLRequestBuilder,
        as type: Response.Type
    ) async throws -> Response {
        try await send(builder, as: type, defaultValue: nil)!
    }

    func send<Response: Decodable>(
        _ builder: URLRequestBuilder,
        as type: Response.Type,
        defaultValue: Response?
    ) async throws -> Response? {
        let request = try builder.build()
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw APIError.unknown()
        }
        guard (200...299).contains(http.statusCode) else {
            throw try decoder(APIError.self, from: data) ?? APIError.unknown("HTTP \(http.statusCode).")
        }
        return try decoder(type, from: data) ?? defaultValue
    }

    private func decoder<T: Decodable>(_ type: T.Type, from data: Data) throws -> T? {
        guard !data.isEmpty else { return nil }
        do {
            let envelope = try JSONDecoder.api.decode(APIEnvelope<T>.self, from: data)
            return envelope.data ?? envelope.value
        } catch {
            return try JSONDecoder.api.decode(type, from: data)
        }
    }
}

private struct APIEnvelope<Data: Decodable>: Decodable {
    let data: Data?
    let value: Data?
}

extension JSONEncoder {
    static var api: JSONEncoder {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        return e
    }
}

extension JSONDecoder {
    static var api: JSONDecoder {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }
}