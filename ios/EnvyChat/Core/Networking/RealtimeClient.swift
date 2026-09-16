import Foundation

/// Raw envelope as received over the socket (data payload kept as JSON dict).
struct RawEnvelope: Decodable {
    let type: String
    let id: String?
    let data: [String: JSONValue]?
    let message: [String: JSONValue]?
    let conversation_id: String?

    func payloadData() -> Data? {
        if let data {
            return try? JSONSerialization.data(withJSONObject: data.mapValues(\.raw))
        }
        if let message {
            return try? JSONSerialization.data(withJSONObject: message.mapValues(\.raw))
        }
        return nil
    }
}

enum JSONValue {
    case string(String), number(Double), bool(Bool), obj([String: JSONValue]), arr([JSONValue])
    var raw: Any {
        switch self {
        case .string(let s): return s
        case .number(let n): return n
        case .bool(let b): return b
        case .obj(let o): return o.mapValues(\.raw)
        case .arr(let a): return a.map(\.raw)
        }
    }
}

extension JSONValue: Decodable {
    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if let s = try? c.decode(String.self) { self = .string(s); return }
        if let b = try? c.decode(Bool.self) { self = .bool(b); return }
        if let n = try? c.decode(Double.self) { self = .number(n); return }
        if let o = try? c.decode([String: JSONValue].self) { self = .obj(o); return }
        if let a = try? c.decode([JSONValue].self) { self = .arr(a); return }
        throw DecodingError.dataCorrupted(.init(codingPath: c.codingPath, debugDescription: "no value"))
    }
}

@Observable
final class RealtimeClient {
    enum State { case disconnected, connecting, connected }

    private(set) var state: State = .disconnected
    var onEnvelope: ((String, Data?) -> Void)?

    private var task: URLSessionWebSocketTask?
    private var subscribedIDs: [String] = []
    private let session = SessionStore.shared

    func connect(conversationIDs: [String]) {
        guard state != .connected else { return }
        subscribedIDs = conversationIDs
        guard let token = session.accessToken,
              let url = URL(string: api().baseURL.replacingOccurrences(of: "http", with: "ws") + "/v1/ws?token=\(token)") else { return }
        state = .connecting
        task = URLSession.shared.webSocketTask(with: url)
        guard let task else { return }
        task.resume()
        send(["type": "subscribe", "conversation_ids": conversationIDs])
        listen()
        state = .connected
    }

    func send(_ json: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: json),
              let text = String(data: data, encoding: .utf8) else { return }
        task?.send(.string(text)) { _ in }
        if state == .connecting { state = .connected }
    }

    func disconnect() {
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
        state = .disconnected
    }

    private func listen() {
        task?.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let message):
                if case .string(let text) = message, let data = text.data(using: .utf8),
                   let envelope = try? JSONDecoder.api.decode(RawEnvelope.self, from: data) {
                    self.onEnvelope?(envelope.type, envelope.payloadData())
                }
                self.listen()
            case .failure:
                self.state = .disconnected
            }
        }
    }

    private func api() -> APIClient { .shared }
}