import SwiftUI

/// Design tokens. Flat colors only — no gradients anywhere in EnvyChat.
enum Theme {
    enum Palette {
        static let brand = Color(red: 0.93, green: 0.55, blue: 0.66)          // baby pink
        static let brandDark = Color(red: 0.78, green: 0.40, blue: 0.53)
        static let accentFlame = Color(red: 0.95, green: 0.45, blue: 0.55)    // soft flame pink
        static let background = Color.white
        static let surface = Color.white
        static let outline = Color(red: 0.94, green: 0.88, blue: 0.90)        // blush outline
        static let textPrimary = Color(red: 0.24, green: 0.20, blue: 0.22)    // soft dark plum
        static let textSecondary = Color(red: 0.62, green: 0.55, blue: 0.58)
        static let success = Color(red: 0.30, green: 0.70, blue: 0.55)
        static let danger = Color(red: 0.85, green: 0.30, blue: 0.38)
        static let bubbleIncoming = Color(red: 0.96, green: 0.92, blue: 0.93) // peek-a-boo blush
        static let bubbleOutgoing = Color(red: 0.93, green: 0.55, blue: 0.66)
        static let flameOn = Color(red: 0.95, green: 0.45, blue: 0.55)
        static let flameOff = Color(red: 0.82, green: 0.80, blue: 0.81)
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

struct CloseToolbarButton: View {
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: "xmark.circle.fill")
                .foregroundStyle(Theme.Palette.textSecondary)
        }
    }
}