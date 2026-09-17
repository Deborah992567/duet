import SwiftUI

/// Calls architecture: architecture-only seam. Real calling is switched on + region-approved
/// production hardware before launch. UI demonstrates the planned call flow.
struct CallSlotsView: View {
    @State private var activeCall: Bool = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .center, spacing: Theme.Metrics.padding) {
                    Image(systemName: "phone.fill")
                        .font(.system(size: 56))
                        .foregroundStyle(Theme.Palette.brand)
                        .padding(.top, Theme.Metrics.padding * 3)

                    Text("Calls are coming soon")
                        .font(Theme.Typography.headline)
                        .foregroundStyle(Theme.Palette.textPrimary)

                    Text("Planned architecture:\nRTC peer-to-peer audio + WebSocket signaling, "
                         + "same-device handoff, and batched presence. "
                         + "Tap-to-talk voice messages already work in chat.")
                        .font(Theme.Typography.body)
                        .foregroundStyle(Theme.Palette.textSecondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, Theme.Metrics.padding)

                    Button {
                        activeCall = true
                    } label: {
                        Label("Preview call screen", systemImage: "phone.circle.fill")
                            .foregroundStyle(.white)
                            .padding(.horizontal, 20)
                            .padding(.vertical, 12)
                            .background(Theme.Palette.brand)
                            .clipShape(Capsule())
                    }

                    Row(title: "Audio", detail: "WebRTC, encrypted")
                    Row(title: "Signaling", detail: "In-app WebSocket channel")
                    Row(title: "Record", detail: "Held in the call summary")
                    Row(title: "Availability", detail: "Activated per region at launch")

                    CallHistoryView()
                        .padding(.top, Theme.Metrics.padding)
                }
                .padding(.horizontal, Theme.Metrics.padding)
            }
            .background(Theme.Palette.background)
            .navigationTitle("Calls")
            .sheet(isPresented: $activeCall) {
                CallPreviewView()
            }
        }
    }
}

private struct CallHistoryView: View {
    @State private var calls: [CallOut] = []

    var body: some View {
        VStack(alignment: .leading, spacing: Theme.Metrics.small) {
            Text("Recent calls")
                .font(Theme.Typography.headline)
                .foregroundStyle(Theme.Palette.textPrimary)
                .frame(maxWidth: .infinity, alignment: .leading)

            if calls.isEmpty {
                Text("No calls yet — your call history will appear here.")
                    .font(Theme.Typography.body)
                    .foregroundStyle(Theme.Palette.textSecondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(Theme.Metrics.padding)
                    .cardStyle()
            } else {
                ForEach(calls.prefix(10)) { call in
                    HStack(spacing: Theme.Metrics.small) {
                        Image(systemName: call.direction == "incoming" ? "arrow.down.left" : "arrow.up.right")
                            .font(.subheadline)
                            .foregroundStyle(call.state == "ended" ? Theme.Palette.textSecondary : Theme.Palette.brand)
                            .frame(width: 24)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(call.peerDisplay)
                                .font(Theme.Typography.body)
                                .foregroundStyle(Theme.Palette.textPrimary)
                            Text(call.durationLabel)
                                .font(Theme.Typography.caption)
                                .foregroundStyle(Theme.Palette.textSecondary)
                        }
                        Spacer()
                        Text(call.sentAt.relativeFormatted)
                            .font(Theme.Typography.caption)
                            .foregroundStyle(Theme.Palette.textSecondary)
                    }
                    .padding(.horizontal, Theme.Metrics.padding)
                    .padding(.vertical, 10)
                    .cardStyle()
                }
            }
        }
        .task { await load() }
    }

    private func load() async {
        let client = APIClient.shared
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/calls/history")
        calls = (try? await client.send(builder, as: CallList.self, defaultValue: nil))?.items ?? []
    }
}

struct CallOut: Decodable, Identifiable, Hashable {
    let id: String
    let kind: String
    let direction: String
    let state: String
    let peerID: String
    let sentAt: Date
    let durationSeconds: Int?

    enum CodingKeys: String, CodingKey {
        case id, kind, direction, state
        case peerID = "peer_user_id"
        case sentAt = "created_at"
        case durationSeconds = "duration_seconds"
    }

    var peerDisplay: String {
        String(peerID.prefix(8)) + "…"
    }

    var durationLabel: String {
        if let d = durationSeconds, d > 0 {
            return "\(d / 60)m \(String(format: "%02d", d % 60))s"
        }
        return state == "ended" ? "Not answered" : "In progress"
    }
}

struct CallList: Decodable {
    let items: [CallOut]
    let hasMore: Bool

    enum CodingKeys: String, CodingKey {
        case items
        case hasMore = "has_more"
    }
}

private struct Row: View {
    let title: String
    let detail: String

    var body: some View {
        HStack {
            Text(title).font(Theme.Typography.body).foregroundStyle(Theme.Palette.textPrimary)
            Spacer()
            Text(detail).font(Theme.Typography.caption).foregroundStyle(Theme.Palette.textSecondary)
        }
        .padding(Theme.Metrics.padding)
        .cardStyle()
    }
}

struct CallPreviewView: View {
    @Environment(\.dismiss) private var dismiss
    @State private var muted = false
    @State private var speaker = true

    var body: some View {
        VStack(spacing: Theme.Metrics.padding * 2) {
            Spacer()
            ZStack {
                Circle().fill(Theme.Palette.bubbleIncoming).frame(width: 120, height: 120)
                Image(systemName: "person.fill")
                    .font(.system(size: 52))
                    .foregroundStyle(Theme.Palette.brand)
            }
            Text("Ava")
                .font(.title3.bold())
                .foregroundStyle(Theme.Palette.textPrimary)
            Text("Calling…")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.textSecondary)
            Spacer()
            HStack(spacing: Theme.Metrics.padding * 2) {
                roundButton(system: muted ? "mic.slash.fill" : "mic.fill", tint: muted ? Theme.Palette.textSecondary : Theme.Palette.brand) {
                    muted.toggle()
                }
                roundButton(system: speaker ? "speaker.wave.2.fill" : "speaker.slash.fill", tint: Theme.Palette.brand) {
                    speaker.toggle()
                }
            }
            roundButton(system: "phone.down.fill", tint: .white) {
                dismiss()
            }
            .padding(.horizontal, 28).padding(.vertical, 18)
            .background(Theme.Palette.danger)
            .clipShape(Circle())
            .padding(.bottom, 40)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.Palette.background)
    }

    private func roundButton(system: String, tint: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: system)
                .font(.system(size: 24))
                .foregroundStyle(tint)
                .padding(18)
                .background(Theme.Palette.bubbleIncoming)
                .clipShape(Circle())
        }
    }
}