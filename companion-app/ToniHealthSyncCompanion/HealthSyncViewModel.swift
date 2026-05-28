import Foundation
import SwiftUI

@MainActor
final class HealthSyncViewModel: ObservableObject {
    static let shared = HealthSyncViewModel()

    @AppStorage("endpointURLString") var endpointURLString: String = "https://toni-fitness-dashboard.onrender.com/api/live-health"
    @Published var isAuthorized = false
    @Published var isSyncing = false
    @Published var lastMessage = "Not synced yet."
    @Published var latestSummary: DailyHealthSummary?

    private let healthStore = HealthStore()
    private let syncService = SyncService()

    func authorize() async {
        guard healthStore.isAvailable else {
            lastMessage = "Health data is not available on this device."
            return
        }
        do {
            try await healthStore.requestAuthorization()
            healthStore.enableBackgroundDelivery()
            healthStore.startObservingBackgroundChanges { [weak self] in
                guard let self else { return }
                _ = await self.syncCurrentSummary(note: "Background sync from HealthKit update.")
            }
            isAuthorized = true
            lastMessage = "Health access granted."
        } catch {
            lastMessage = "Authorization failed: \(error.localizedDescription)"
        }
    }

    func loadToday() async {
        do {
            latestSummary = try await healthStore.fetchTodaySummary()
            lastMessage = "Loaded today's Health data."
        } catch {
            lastMessage = "Failed to load data: \(error.localizedDescription)"
        }
    }

    func syncNow() async {
        _ = await syncCurrentSummary(note: "Synced from iPhone companion app.")
    }

    func syncInBackground() async -> Bool {
        await syncCurrentSummary(note: "Background sync from iPhone companion app.")
    }

    var dashboardURL: URL? {
        backendBaseURL?.appendingPathComponent("index.html")
    }

    var planURL: URL? {
        backendBaseURL?.appendingPathComponent("plan.html")
    }

    private var backendBaseURL: URL? {
        guard let url = URL(string: endpointURLString) else {
            return nil
        }
        let apiBase = url.deletingLastPathComponent().deletingLastPathComponent()
        return apiBase
    }

    private func syncCurrentSummary(note: String) async -> Bool {
        guard let url = URL(string: endpointURLString) else {
            lastMessage = "Invalid endpoint URL."
            return false
        }

        isSyncing = true
        defer { isSyncing = false }

        do {
            let summary = try await healthStore.fetchTodaySummary()
            latestSummary = summary
            let payload = summary.asPayload(source: "Toni Health Sync Companion", notes: note)
            try await syncService.postSummary(payload, endpointURL: url)
            lastMessage = note.contains("Background") ? "Background sync complete." : "Sync complete."
            return true
        } catch {
            lastMessage = "Sync failed: \(error.localizedDescription)"
            return false
        }
    }
}
