import Foundation
import AVFoundation
import CryptoKit
import Observation

struct BeginUploadBody: Encodable {
    let kind: String
    let file_name: String
    let size_bytes: Int
    let mime_type: String
    let checksum_sha256: String
}

/// Records a voice/talk message.
@MainActor
@Observable
final class VoiceRecorder: NSObject, AVAudioRecorderDelegate {
    private(set) var isRecording = false
    private var recorder: AVAudioRecorder?
    var onFinished: ((URL) -> Void)?

    func start() {
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playAndRecord, mode: .default)
            try session.setActive(true)

            let url = FileManager.default.temporaryDirectory.appendingPathComponent("talk-\(UUID().uuidString).m4a")
            let settings: [String: Any] = [
                AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
                AVSampleRateKey: 44100,
                AVNumberOfChannelsKey: 1,
                AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue,
            ]
            let rec = try AVAudioRecorder(url: url, settings: settings)
            rec.delegate = self
            rec.isMeteringEnabled = true
            rec.record()
            recorder = rec
            isRecording = true
        } catch {
            isRecording = false
        }
    }

    func stop() {
        guard let rec = recorder else { return }
        let url = rec.url
        rec.stop()
        isRecording = false
        recorder = nil
        if rec.currentTime > 0.5 {
            onFinished?(url)
        }
    }

    nonisolated func audioRecorderDidFinishRecording(_ recorder: AVAudioRecorder, successfully flag: Bool) {
        Task { @MainActor in
            isRecording = false
            self.recorder = nil
        }
    }
}

/// Uploads a recorded audio file through the media seam:
/// begin → PUT content → complete → returns the attachment's upload_id.
struct MediaUploader {
    let client = APIClient.shared

    struct BeginResponse: Decodable {
        let upload_id: String
        let upload_url: String?
    }

    func uploadVoice(url: URL, kind: String = "voice") async -> String? {
        guard let token = SessionStore.shared.accessToken else { return nil }
        let size = (try? FileManager.default.attributesOfItem(atPath: url.path)[.size] as? Int) ?? 0
        let data = (try? Data(contentsOf: url)) ?? Data()

        var begin = URLRequestBuilder(base: client.baseURL, path: "/v1/media/uploads", method: .post)
        begin.token = token
        begin.body = BeginUploadBody(
            kind: kind,
            file_name: url.lastPathComponent,
            size_bytes: size,
            mime_type: "audio/mp4",
            checksum_sha256: SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        )
        guard let response: BeginResponse = try? await client.send(begin, as: BeginResponse.self) else { return nil }

        var put = URLRequestBuilder(base: client.baseURL, path: "/v1/media/\(response.upload_id)/content", method: .put)
        put.token = token
        guard let putRequest = try? put.build() else { return nil }
        var resolved = putRequest
        resolved.httpBody = data
        resolved.setValue("application/octet-stream", forHTTPHeaderField: "Content-Type")
        guard let (_, response2) = try? await URLSession.shared.data(for: resolved),
              (response2 as? HTTPURLResponse)?.statusCode == 201 else { return nil }

        var complete = URLRequestBuilder(base: client.baseURL, path: "/v1/media/uploads/\(response.upload_id)/complete", method: .post)
        complete.token = token
        guard let completion: [String: String] = try? await client.send(complete, as: [String: String].self, defaultValue: nil) else { return nil }
        _ = completion
        return response.upload_id
    }
}

/// AVAudioPlayer wrapper that exposes playback state for voice bubbles.
@MainActor
@Observable
final class VoicePlayer: NSObject, AVAudioPlayerDelegate {
    private(set) var isPlaying = false
    private var activeURL: URL?
    private var player: AVAudioPlayer?

    func toggle(url: URL) {
        if isPlaying && activeURL == url {
            player?.stop()
            isPlaying = false
            return
        }
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .spokenAudio)
            try session.setActive(true)
            let player = try AVAudioPlayer(contentsOf: url)
            player.delegate = self
            player.play()
            self.player = player
            activeURL = url
            isPlaying = true
        } catch {
            isPlaying = false
        }
    }

    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in
            self.isPlaying = false
        }
    }
}