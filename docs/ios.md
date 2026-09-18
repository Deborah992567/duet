# iOS notes

## Build

```bash
cd ios
xcodegen generate
xcodebuild -project Duet.xcodeproj -scheme Duet \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  build CODE_SIGNING_ALLOWED=NO
```

Run tests the same way with `test` instead of `build` (19 unit tests).

- Target: iPhone only (`TARGETED_DEVICE_FAMILY=1`), iOS 17+, Swift 5.10.
- No gradients, flat baby-pink + white design tokens in `Design/Theme.swift`.
- `API_BASE_URL` environment variable overrides the dev endpoint at runtime.

## Features

- Inbox: conversation rows, unread badges, typing + presence dots.
- Chat: text/images/voice, quote replies, forwarding, message search,
  reactions (tap a chip to remove your emoji), edit/delete, read receipts,
  typing emission, streak banner.
- Streaks: leaderboard, animated flame detail (live `between` stats),
  30-day history strip, milestones.
- Calls tab: architecture preview + real call-history feed.
- Friends: requests, search, add/respond, user profiles, block/unblock.
- Notifications: in-app feed + per-channel preferences.
- Profile: streak toggles, notification prefs, sign out, clear local cache.
- First-run onboarding, push-authorization seam (simulator-safe), outbox retry.

## Networking

- `APIClient` unwraps `{data:…}` / `{value:…}` envelopes automatically.
- `URLRequestBuilder` encodes query + JSON body and injects the Bearer token.
- `RealtimeClient` decodes WS frames with `RawEnvelope` + `JSONValue`
  (handles both object and array payloads).

## Persistence (offline-first)

- `LocalStore` (SwiftData): `ConversationCache`, `MessageCache`, `OutboxEntry`.
- Chat hydrates from cache, refines from history, queues failures, and retries
  the outbox after connecting the socket. Profile can clear the whole cache.

## Voice & media

- `VoiceRecorder` (AVAudioRecorder) → m4a; `VoicePlayer` for playback.
- Voice/image messages upload through the media seam
  (`POST /v1/media/uploads` → `PUT …/content` → `…/complete`) and render as
  waveform/image bubbles with playback.

## Not yet wired

- Push notifications (backend `push-token` endpoint exists; APNs registration
  is a simulator-safe no-op until a distribution certificate is added).
- RTC calling (architecture-only preview + call-history feed).