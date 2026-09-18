import SwiftUI

struct StreakBetweenResponse: Decodable {
    let currentStreak: Int
    let longestStreak: Int
    let alive: Bool
    let freezesAvailable: Int
    let preparedAt: String?
    let milestonesReached: [Int]
    let closestMilestone: Int?

    enum CodingKeys: String, CodingKey {
        case alive
        case currentStreak = "current_streak"
        case longestStreak = "longest_streak"
        case freezesAvailable = "freezes_available"
        case preparedAt = "prepared_at"
        case milestonesReached = "milestones_reached"
        case closestMilestone = "closest_milestone"
    }
}

struct StreakHistoryItem: Decodable, Hashable {
    let eventType: String
    let day: String
    let streakAfter: Int

    enum CodingKeys: String, CodingKey {
        case day
        case eventType = "event_type"
        case streakAfter = "streak_after"
    }
}

/// Streak detail backed by the live `between` endpoint (engine stats).
struct StreakDetailView: View {
    let conversation: ConversationSummary
    @State private var streak: StreakBetweenResponse?
    @State private var loaded = false
    @State private var history: [StreakHistoryItem] = []

    private let milestones = [7, 30, 100, 365, 500, 1000]

    private var current: Int { streak?.currentStreak ?? conversation.currentStreak }
    private var isAlive: Bool { conversation.streakAlive || (streak?.alive ?? false) || current > 0 }

    var body: some View {
        VStack(spacing: Theme.Metrics.padding) {
            Spacer()
            AnimatedFlame(size: 120, isAlive: isAlive)
            Text("\(current)")
                .font(.system(size: 64, weight: .heavy, design: .rounded))
                .foregroundStyle(Theme.Palette.flameOn)
            Text(current == 1 ? "day on a roll" : "days on a roll")
                .font(Theme.Typography.headline)
                .foregroundStyle(Theme.Palette.textPrimary)

            if loaded {
                statChips
            }

            historyStrip
                .padding(.horizontal, Theme.Metrics.padding)

            VStack(spacing: Theme.Metrics.small) {
                ForEach(milestones, id: \.self) { milestone in
                    milestoneRow(milestone)
                }
            }
            .padding(.horizontal, Theme.Metrics.padding)

            Text("Both of you need to send at least one message every day. Missing a day ends the streak.")
                .font(Theme.Typography.caption)
                .foregroundStyle(Theme.Palette.textSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, Theme.Metrics.padding * 2)

            Spacer()
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Theme.Palette.background)
        .navigationTitle(conversation.name ?? conversation.peer?.username ?? "Streak")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private var statChips: some View {
        HStack(spacing: Theme.Metrics.small) {
            chip(title: "Longest", value: "\(streak?.longestStreak ?? 0)")
            chip(title: "Freezes", value: "\(streak?.freezesAvailable ?? 0)")
        }
        .padding(.horizontal, Theme.Metrics.padding)
    }

    private func chip(title: String, value: String) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.system(size: 20, weight: .bold)).foregroundStyle(Theme.Palette.brand)
            Text(title).font(Theme.Typography.caption).foregroundStyle(Theme.Palette.textSecondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, Theme.Metrics.padding)
        .cardStyle()
    }

    private func milestoneRow(_ milestone: Int) -> some View {
        HStack {
            Text("\(milestone)-day streak")
                .font(Theme.Typography.body)
                .foregroundStyle(Theme.Palette.textPrimary)
            Spacer()
            if current >= milestone {
                Image(systemName: "checkmark.seal.fill")
                    .foregroundStyle(Theme.Palette.brand)
            } else {
                Text("\(milestone - current) days to go")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.textSecondary)
            }
        }
        .padding(Theme.Metrics.padding)
        .cardStyle()
    }

    private var historyStrip: some View {
        VStack(alignment: .leading, spacing: Theme.Metrics.small) {
            Text("Last 30 days")
                .font(Theme.Typography.headline)
                .foregroundStyle(Theme.Palette.textPrimary)
            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 6), count: 10), spacing: 6) {
                ForEach(last30Days, id: \.self) { day in
                    Circle()
                        .fill(color(for: day))
                        .frame(height: 20)
                }
            }
            HStack {
                legendDot(Theme.Palette.success, label: "Both sent")
                legendDot(Theme.Palette.brand, label: "Freeze used")
                legendDot(Theme.Palette.flameOff.opacity(0.35), label: "No send")
            }
            .font(Theme.Typography.caption)
            .foregroundStyle(Theme.Palette.textSecondary)
        }
        .padding(Theme.Metrics.padding)
        .cardStyle()
    }

    private var last30Days: [Date] {
        let calendar = Calendar.current
        let today = calendar.startOfDay(for: Date())
        return (0..<30).map { calendar.date(byAdding: .day, value: -$0, to: today) ?? today }.reversed()
    }

    private func color(for date: Date) -> Color {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.calendar = Calendar(identifier: .gregorian)
        let key = formatter.string(from: date)
        for entry in history where entry.day == key {
            switch entry.eventType {
            case "freeze_used": return Theme.Palette.brand
            case "incremented": return Theme.Palette.success
            case "broken": return .red.opacity(0.65)
            default: continue
            }
        }
        return Theme.Palette.flameOff.opacity(0.35)
    }

    private func legendDot(_ color: Color, label: String) -> some View {
        HStack(spacing: 4) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(label)
        }
    }

    private func load() async {
        guard let peerID = conversation.peer?.id else { return }
        let client = APIClient.shared
        let builder = URLRequestBuilder(base: client.baseURL, path: "/v1/streaks/\(conversation.id)/with/\(peerID)")
        if let response: StreakBetweenResponse = try? await client.send(builder, as: StreakBetweenResponse.self) {
            streak = response
        }
        let historyBuilder = URLRequestBuilder(base: client.baseURL, path: "/v1/streaks/history/\(conversation.id)/with/\(peerID)")
        if let response: HistoryResponse = try? await client.send(historyBuilder, as: HistoryResponse.self) {
            history = response.items
        }
        loaded = true
    }
}

struct HistoryResponse: Decodable {
    let items: [StreakHistoryItem]
}

struct AnimatedFlame: View {
    let size: CGFloat
    let isAlive: Bool

    var body: some View {
        Image(systemName: "flame.fill")
            .font(.system(size: size))
            .foregroundStyle(isAlive ? Theme.Palette.flameOn : Theme.Palette.flameOff)
            .phaseAnimator([0, 1, 0]) { view, phase in
                view
                    .scaleEffect(isAlive ? 1 + 0.06 * phase : 1)
                    .offset(y: isAlive ? -3 * phase : 0)
            } animation: { _ in
                .easeInOut(duration: 0.8)
            }
    }
}