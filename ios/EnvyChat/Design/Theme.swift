import SwiftUI

/// Design tokens. Flat colors only — no gradients anywhere in EnvyChat.
enum Theme {
    enum Palette {
        static let brand = Color(red: 0.16, green: 0.42, blue: 0.95)
        static let brandDark = Color(red: 0.10, green: 0.29, blue: 0.68)
        static let accentFlame = Color(red: 0.96, green: 0.36, blue: 0.23) // streaks
        static let background = Color(red: 0.97, green: 0.97, blue: 0.98)
        static let surface = Color.white
        static let outline = Color(red: 0.86, green: 0.87, blue: 0.89)
        static let textPrimary = Color(red: 0.10, green: 0.12, blue: 0.14)
        static let textSecondary = Color(red: 0.47, green: 0.50, blue: 0.53)
        static let success = Color(red: 0.18, green: 0.65, blue: 0.35)
        static let danger = Color(red: 0.85, green: 0.24, blue: 0.24)
        static let bubbleIncoming = Color(red: 0.93, green: 0.94, blue: 0.96)
        static let bubbleOutgoing = Color(red: 0.16, green: 0.42, blue: 0.95)
        static let flameOn = Color(red: 0.96, green: 0.36, blue: 0.23)
        static let flameOff = Color(red: 0.68, green: 0.71, blue: 0.74)
    }

    enum Metrics {
        static let radius: CGFloat = 14
        static let radiusSmall: CGFloat = 10
        static let padding: CGFloat = 16
        static let small: CGFloat = 8
        static let lineWidth: CGFloat = 1
    }

    enum Typography {
        static let title = Font.system(size: 28, weight: .bold)
        static let headline = Font.system(size: 20, weight: .semibold)
        static let body = Font.system(size: 16, weight: .regular)
        static let caption = Font.system(size: 13, weight: .regular)
        static let streak = Font.system(size: 34, weight: .heavy)
    }
}

extension View {
    func cardStyle() -> some View {
        self
            .background(Theme.Palette.surface)
            .clipShape(RoundedRectangle(cornerRadius: Theme.Metrics.radius, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: Theme.Metrics.radius, style: .continuous)
                    .stroke(Theme.Palette.outline, lineWidth: Theme.Metrics.lineWidth)
            )
    }
}