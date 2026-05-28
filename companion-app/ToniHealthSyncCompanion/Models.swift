import Foundation

struct WorkoutPayload: Codable, Identifiable {
    let id = UUID()
    let type: String
    let start: String
    let durationMin: Double
    let distanceKm: Double?
}

struct HealthMetricsPayload: Codable {
    let steps: Double?
    let active_kcal: Double?
    let resting_hr: Double?
    let hrv: Double?
    let sleep_hours: Double?
    let body_mass_kg: Double?
    let vo2max: Double?
}

struct DailyHealthPayload: Codable {
    let date: String
    let source: String
    let metrics: HealthMetricsPayload
    let workouts: [WorkoutPayload]
    let notes: String?
}

struct DailyHealthSummary {
    let date: Date
    let steps: Double?
    let activeKcal: Double?
    let restingHR: Double?
    let hrv: Double?
    let sleepHours: Double?
    let bodyMassKg: Double?
    let vo2max: Double?
    let workouts: [WorkoutPayload]

    func asPayload(source: String, notes: String?) -> DailyHealthPayload {
        DailyHealthPayload(
            date: Self.dateFormatter.string(from: date),
            source: source,
            metrics: HealthMetricsPayload(
                steps: steps,
                active_kcal: activeKcal,
                resting_hr: restingHR,
                hrv: hrv,
                sleep_hours: sleepHours,
                body_mass_kg: bodyMassKg,
                vo2max: vo2max
            ),
            workouts: workouts,
            notes: notes
        )
    }

    private static let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.calendar = Calendar(identifier: .gregorian)
        formatter.locale = Locale(identifier: "en_GB")
        formatter.dateFormat = "yyyy-MM-dd"
        return formatter
    }()
}
