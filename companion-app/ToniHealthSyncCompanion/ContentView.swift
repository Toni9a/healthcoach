import SwiftUI
import WebKit

struct ContentView: View {
    @EnvironmentObject private var viewModel: HealthSyncViewModel
    @State private var selectedTab = 0

    var body: some View {
        TabView(selection: $selectedTab) {
            NavigationStack {
                Form {
                    Section("Backend") {
                        TextField("Endpoint URL", text: $viewModel.endpointURLString)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .keyboardType(.URL)
                    }

                    Section("Health Access") {
                        Button("Authorize Health Access") {
                            Task { await viewModel.authorize() }
                        }

                        Button("Load Today's Data") {
                            Task { await viewModel.loadToday() }
                        }
                        .disabled(!viewModel.isAuthorized)

                        Button(viewModel.isSyncing ? "Syncing..." : "Sync Now") {
                            Task { await viewModel.syncNow() }
                        }
                        .disabled(!viewModel.isAuthorized || viewModel.isSyncing)
                    }

                    if let summary = viewModel.latestSummary {
                        Section("Today's Summary") {
                            summaryRow("Steps", value: summary.steps)
                            summaryRow("Active kcal", value: summary.activeKcal)
                            summaryRow("Resting HR", value: summary.restingHR)
                            summaryRow("HRV", value: summary.hrv)
                            summaryRow("Sleep hours", value: summary.sleepHours)
                            summaryRow("Weight kg", value: summary.bodyMassKg)
                            summaryRow("VO2max", value: summary.vo2max)
                        }

                        if !summary.workouts.isEmpty {
                            Section("Workouts") {
                                ForEach(summary.workouts) { workout in
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(workout.type).font(.headline)
                                        Text("Duration: \(workout.durationMin, specifier: "%.0f") min")
                                        if let km = workout.distanceKm {
                                            Text("Distance: \(km, specifier: "%.2f") km")
                                        }
                                    }
                                }
                            }
                        }
                    }

                    Section("Status") {
                        Text(viewModel.lastMessage)
                            .foregroundStyle(.secondary)
                    }
                }
                .navigationTitle("Health Sync")
            }
            .tabItem {
                Label("Sync", systemImage: "heart.text.square")
            }
            .tag(0)

            NavigationStack {
                DashboardWebView(
                    title: "Dashboard",
                    url: viewModel.dashboardURL
                )
                .navigationTitle("Dashboard")
            }
            .tabItem {
                Label("Dashboard", systemImage: "rectangle.on.rectangle")
            }
            .tag(1)

            NavigationStack {
                DashboardWebView(
                    title: "Plan",
                    url: viewModel.planURL
                )
                .navigationTitle("Plan")
            }
            .tabItem {
                Label("Plan", systemImage: "calendar")
            }
            .tag(2)
        }
    }

    @ViewBuilder
    private func summaryRow(_ label: String, value: Double?) -> some View {
        HStack {
            Text(label)
            Spacer()
            Text(value.map { String(format: "%.1f", $0) } ?? "n/a")
                .foregroundStyle(.secondary)
        }
    }
}

private struct DashboardWebView: View {
    let title: String
    let url: URL?

    var body: some View {
        Group {
            if let url {
                WebView(url: url)
                    .ignoresSafeArea(edges: .bottom)
            } else {
                ContentUnavailableView(
                    "\(title) unavailable",
                    systemImage: "globe",
                    description: Text("Set the backend URL in the Sync tab so the app can load the dashboard.")
                )
            }
        }
    }
}

private struct WebView: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.allowsBackForwardNavigationGestures = true
        webView.load(URLRequest(url: url))
        return webView
    }

    func updateUIView(_ webView: WKWebView, context: Context) {
        if webView.url != url {
            webView.load(URLRequest(url: url))
        }
    }
}
