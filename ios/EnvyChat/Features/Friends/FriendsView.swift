import SwiftUI

struct FriendsView: View {
    @State private var store = FriendsStore()
    @State private var query = ""
    @State private var tab: Tab = .friends

    enum Tab: String, CaseIterable {
        case friends = "Friends"
        case requests = "Requests"
        case add = "Add"
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                Picker("", selection: $tab) {
                    ForEach(Tab.allCases, id: \.self) { t in Text(t.rawValue).tag(t) }
                }
                .pickerStyle(.segmented)
                .padding(Theme.Metrics.padding)

                switch tab {
                case .friends: friendsList
                case .requests: requestsList
                case .add: searchList
                }
            }
            .background(Theme.Palette.background)
            .navigationTitle("People")
            .task { await store.refresh() }
            .refreshable { await store.refresh() }
        }
    }

    private var friendsList: some View {
        ScrollView {
            LazyVStack(spacing: Theme.Metrics.small) {
                if store.friends.isEmpty {
                    Text("No friends yet. Add someone to start a streak.")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.textSecondary)
                        .padding()
                }
                ForEach(store.friends) { entry in
                    shareRow(user: entry.user)
                }
            }
            .padding(.horizontal, Theme.Metrics.padding)
        }
    }

    private var requestsList: some View {
        ScrollView {
            LazyVStack(spacing: Theme.Metrics.small) {
                if store.incomingRequests.isEmpty {
                    Text("No pending requests.")
                        .font(Theme.Typography.caption)
                        .foregroundStyle(Theme.Palette.textSecondary)
                        .padding()
                }
                ForEach(store.incomingRequests) { request in
                    HStack(spacing: Theme.Metrics.padding) {
                        avatar(for: request.sender.name)
                        VStack(alignment: .leading) {
                            Text(request.sender.name).font(Theme.Typography.body)
                            if let message = request.message, !message.isEmpty {
                                Text(message).font(Theme.Typography.caption).foregroundStyle(Theme.Palette.textSecondary)
                            }
                        }
                        Spacer()
                        Button("Accept") {
                            Task { await store.respond(requestID: request.id, accept: true) }
                        }
                        .font(.subheadline.bold())
                        .foregroundStyle(.white)
                        .padding(.horizontal, 12).padding(.vertical, 6)
                        .background(Theme.Palette.brand)
                        .clipShape(Capsule())
                        Button("Decline") {
                            Task { await store.respond(requestID: request.id, accept: false) }
                        }
                        .font(.subheadline)
                        .foregroundStyle(Theme.Palette.textSecondary)
                    }
                    .padding(Theme.Metrics.padding)
                    .cardStyle()
                }
            }
            .padding(.horizontal, Theme.Metrics.padding)
        }
    }

    private var searchList: some View {
        VStack(spacing: 0) {
            HStack {
                Image(systemName: "magnifyingglass").foregroundStyle(Theme.Palette.textSecondary)
                TextField("Search by username", text: $query)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .onChange(of: query) { _, q in Task { await store.search(q) } }
            }
            .padding(Theme.Metrics.padding)
            .background(Theme.Palette.surface)
            .clipShape(RoundedRectangle(cornerRadius: Theme.Metrics.radiusSmall, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: Theme.Metrics.radiusSmall, style: .continuous).stroke(Theme.Palette.outline, lineWidth: 1))
            .padding(Theme.Metrics.padding)

            ScrollView {
                LazyVStack(spacing: Theme.Metrics.small) {
                    ForEach(store.searchResults) { user in
                        shareRow(user: user) {
                            Task { await store.sendRequest(to: user.id) }
                        }
                    }
                }
                .padding(.horizontal, Theme.Metrics.padding)
            }
        }
    }

    private func shareRow(user: FriendUser, action: (() -> Void)? = nil) -> some View {
        HStack(spacing: Theme.Metrics.padding) {
            avatar(for: user.name)
            VStack(alignment: .leading) {
                Text(user.name).font(Theme.Typography.body)
                Text("@\(user.username)")
                    .font(Theme.Typography.caption)
                    .foregroundStyle(Theme.Palette.textSecondary)
            }
            Spacer()
            if let action {
                Button(action: action) {
                    Image(systemName: "person.crop.circle.badge.plus")
                        .foregroundStyle(Theme.Palette.brand)
                        .font(.title3)
                }
            } else if user.isOnline ?? false {
                Circle().fill(Theme.Palette.success).frame(width: 10, height: 10)
            }
        }
        .padding(Theme.Metrics.padding)
        .cardStyle()
    }

    private func avatar(for name: String) -> some View {
        ZStack {
            Circle().fill(Theme.Palette.bubbleIncoming).frame(width: 44, height: 44)
            Text(String(name.prefix(1)).uppercased())
                .font(.headline)
                .foregroundStyle(Theme.Palette.brand)
        }
    }
}