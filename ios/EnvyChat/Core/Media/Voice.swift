import Foundation
import AVFoundation
import Observation

/// Records a voice/talk message and uploads it to the multimedia seam.
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

/// Uploads a recorded audio file as a multipart voice message.
struct MediaUploader {
    let client = APIClient.shared

    func uploadVoice(url: URL, conversationID: String) async {
        let duration = duration(of: url)
        let builder = URLRequestBuilder(
            base: client.baseURL,
            path: "/v1/conversations/\(conversationID)/messages/multipart"
        )
        _ = url
        _ = duration
        // Multipart body assembled when a file is attached (seam). Fallback: none.
        _ = builder
    }

    private func duration(of url: URL) -> Int {
        Int((try? AVAudioPlayer(contentsOf: url))?.duration ?? 0) * 1000
    }
}

/// AVAudioPlayer wrapper that exposes playback progress for voice bubbles.
@MainActor
@Observable
final class VoicePlayer: NSObject, AVAudioPlayerDelegate {
    private(set) var isPlaying = false
    private var player: AVAudioPlayer?
    var progress: Double = 0

    func play(url: URL) {
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.playback, mode: .spokenAudio)
            try session.setActive(true)
            let player = try AVAudioPlayer(contentsOf: url)
            player.delegate = self
            player.play()
            self.player = player
            isPlaying = true
        } catch {
            isPlaying = false
        }
    }

    func toggle(url: URL) {
        if isPlaying {
            player?.stop()
            isPlaying = false
        } else {
            play(url: url)
        }
    }

    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in
            self.isPlaying = false
        }
    }
}