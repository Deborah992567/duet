# iOS notes

## Build

```bash
cd ios
xcodegen generate
xcodebuild -project EnvyChat.xcodeproj -scheme EnvyChat \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  build CODE_SIGNING_ALLOWED=NO
```

Run tests the same way with `test` instead of `build` (7 unit tests).

- Target: iPhone only (`TARGETED_DEVICE_FAMILY=1`), iOS 17+, Swift 5.10.
- No gradients, flat baby-pink + white design tokens in `Design/Theme.swift`.
- `API_BASE_URL` environment variable overrides the dev endpoint at runtime.

## Networking

- `APIClient` unwraps `{data:…}` / `{value:…}` envelopes automatically.
- `URLRequestBuilder` encodes query + JSON body and injects the Bearer token.
- `RealtimeClient` decodes WS frames with `RawEnvelope` + `JSONValue`
  (handles both object and array payloads).

## Persistence (offline-first)

- `LocalStore` (SwiftData): `ConversationCache`, `MessageCache`, `OutboxEntry`.
- Chat hydrates from cache, refines from history, queues failures, and retries
  the outbox after connecting the socket.

## Voice

- `VoiceRecorder` (AVAudioRecorder) → m4a; `VoicePlayer` for playback.
- Voice messages upload to the multipart seam and render as waveform bubbles.

## Not yet wired

- Push notifications (backend `push-token` endpoint exists; APNs payload comes
  with a distribution certificate).
- RTC calling (architecture-only preview screen).
- Real media upload (iOS uploader scaffolded, server seam defined).