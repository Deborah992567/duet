import SwiftUI

/// Inbox: list of conversations. Empty state until conversations are created.
struct InboxView: View {
    @Environment(AppState.self) private var state

    var body: some View {
        NavigationStack {
            VStack(spacing: Theme.Metrics.padding) {
                if true {
                    emptyState
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
            .background(Theme.Palette.background)
            .navigationTitle("Inbox")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        // Friends list
                    } label: {
                        Image(systemName: "person.2.fill")
                            .foregroundStyle(Theme.Palette.brand)
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        // New message
                    } label: {
                        Image(systemName: "square.and.pencil")
                            .foregroundStyle(Theme.Palette.brand)
                    }
                }
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: Theme.Metrics.small) {
            Image(systemName: "bubble.left.and.bubble.right")
                .font(.system(size: 48))
                .foregroundStyle(Theme.Palette.textSecondary)
            Text("No conversations yet")
                .font(Theme.Typography.headline)
                .foregroundStyle(Theme.Palette.textPrimary)
            Text("Send your first message to start a streak.")
                .font(Theme.Typography.body)
                .foregroundStyle(Theme.Palette.textSecondary)
        }
        .padding(Theme.Metrics.padding)
        .cardStyle()
        .padding(Theme.Metrics.padding)
    }
}