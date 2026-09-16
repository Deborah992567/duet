import SwiftUI

struct MainTabView: View {
    var body: some View {
        TabView {
            InboxView()
                .tabItem { Label("Inbox", systemImage: "bubble.left.and.bubble.right") }
            StreaksView()
                .tabItem { Label("Streaks", systemImage: "flame.fill") }
            ProfileView()
                .tabItem { Label("Profile", systemImage: "person.crop.circle") }
        }
        .tint(Theme.Palette.brand)
    }
}