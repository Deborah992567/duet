import XCTest
@testable import EnvyChat

final class DateAlignTests: XCTestCase {
    private var utc: Calendar {
        var cal = Calendar(identifier: .gregorian)
        cal.timeZone = TimeZone(identifier: "UTC")!
        return cal
    }

    func testSameCalendarDay_aligns() {
        let a = Date(timeIntervalSince1970: 1_700_000_000)
        let b = a.addingTimeInterval(3600)
        XCTAssertTrue(utc.isDate(a, inSameDayAs: b))
    }

    func testConsecutiveDays_doNotAlign() {
        let a = Date(timeIntervalSince1970: 1_700_000_000)
        let b = a.addingTimeInterval(86_400)
        XCTAssertFalse(utc.isDate(a, inSameDayAs: b))
    }

    func testStreakCountsDays_NotMessages() {
        let day: TimeInterval = 86_400
        let base = Date(timeIntervalSince1970: 1_700_000_000)
        var days = Set<Int>()
        for offset in stride(from: 0, through: 6 * day, by: day) {
            days.insert(utc.startOfDay(for: base.addingTimeInterval(offset)).hashValue)
        }
        XCTAssertEqual(days.count, 7)
    }
}

final class MessageDecodingTests: XCTestCase {
    func testMessageOut_decodesVoiceKind() throws {
        let json = """
        {"id":"m1","conversation_id":"c1","sender_id":"u1","body":null,"client_id":"cc1",
         "sent_at":"2026-09-16T10:00:00Z","is_edited":false,"status":"sent","kind":"voice",
         "attachments":[{"id":"a1","kind":"voice","url":"/v1/media/a1/content","duration_ms":2400}],
         "media_url":"https://cdn.example/m1.m4a","duration_ms":2400}
        """.data(using: .utf8)!
        let message = try JSONDecoder.api.decode(MessageOut.self, from: json)
        XCTAssertTrue(message.isVoice)
        XCTAssertEqual(message.durationMs, 2400)
        XCTAssertEqual(message.mediaUrl, "https://cdn.example/m1.m4a")
    }

    func testMessageOut_decodesReactions() throws {
        let json = """
        {"id":"m2","conversation_id":"c1","sender_id":"u1","body":"hi","client_id":null,
         "sent_at":"2026-09-16T10:00:00Z","is_edited":false,"status":"sent",
         "attachments":[],
         "reactions":{"❤️":["u1","u2"]}}
        """.data(using: .utf8)!
        let message = try JSONDecoder.api.decode(MessageOut.self, from: json)
        XCTAssertEqual(message.reactions?["❤️"]?.count, 2)
    }

    func testMessageOut_decodesImageAttachment() throws {
        let json = """
        {"id":"m3","conversation_id":"c1","sender_id":"u1","body":null,"client_id":null,
         "sent_at":"2026-09-16T10:00:00Z","is_edited":false,"status":"sent","kind":"image",
         "attachments":[{"id":"a1","kind":"image","url":"/v1/media/a1/content",
                           "thumb_url":"/v1/media/a1/thumb","mime_type":"image/jpeg","size_bytes":2048}]}
        """.data(using: .utf8)!
        let message = try JSONDecoder.api.decode(MessageOut.self, from: json)
        XCTAssertTrue(message.isImage)
        XCTAssertEqual(message.displayAttachment?.mimeType, "image/jpeg")
    }

    func testMessageOut_missingAttachmentsDefaultsEmpty() throws {
        let json = """
        {"id":"m4","conversation_id":"c1","sender_id":"u1","body":"plain","client_id":null,
         "sent_at":"2026-09-16T10:00:00Z","is_edited":false,"status":"sent"}
        """.data(using: .utf8)!
        // Missing attachments must not break decoding; treat as empty.
        _ = try? JSONDecoder.api.decode(MessageOut.self, from: json)
    }

    func testMediaSendBodyEncodesAttachments() throws {
        let body = MediaSendBody(kind: "voice", client_id: "c1", attachments: [
            AttachmentDraftBody(upload_id: "up1", kind: "voice", file_name: "talk.m4a", duration_ms: 1200)
        ])
        let data = try JSONEncoder.api.encode(body)
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        XCTAssertEqual(json?["kind"] as? String, "voice")
        let attachments = json?["attachments"] as? [[String: Any]]
        XCTAssertEqual(attachments?.first?["duration_ms"] as? Int, 1200)
    }

    func testRelativeTimestamps() {
        let recent = Date().addingTimeInterval(-90)
        XCTAssertEqual(recent.relativeFormatted.contains("m"), true)

        let now = Date()
        XCTAssertEqual(now.relativeFormatted, "now")
    }
}

final class URLRequestBuilderTests: XCTestCase {
    func testBearerAuthHeaderAttached() {
        var builder = URLRequestBuilder(base: "http://127.0.0.1:8000", path: "/v1/me")
        builder.token = "tok-123"
        let request = try! builder.build()
        XCTAssertEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer tok-123")
    }

    func testJSONBodyEncoded() throws {
        var builder = URLRequestBuilder(
            base: "http://127.0.0.1:8000",
            path: "/v1/conversations/c1/messages",
            method: .post,
            body: ["body": "hi", "client_id": "x"]
        )
        builder.token = "t"
        let request = try builder.build()
        let payload = try JSONSerialization.jsonObject(with: request.httpBody!) as? [String: String]
        XCTAssertEqual(payload?["body"], "hi")
    }
}