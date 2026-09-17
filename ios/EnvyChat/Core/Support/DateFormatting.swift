import Foundation

extension Date {
    /// "now", "5m ago", "2h ago", "yesterday", else a short date.
    var relativeFormatted: String {
        let seconds = Date().timeIntervalSince(self)
        if seconds < 60 { return String(localized: "now") }
        if seconds < 3600 { return String(localized: "minutes_ago_short", defaultValue: "\(Int(seconds / 60))m") }
        if seconds < 86_400 { return String(localized: "hours_ago_short", defaultValue: "\(Int(seconds / 3600))h") }
        let formatter = DateFormatter()
        formatter.dateStyle = .short
        formatter.timeStyle = .none
        return formatter.string(from: self)
    }
}