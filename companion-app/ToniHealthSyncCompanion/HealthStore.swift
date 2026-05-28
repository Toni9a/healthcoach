import Foundation
import HealthKit

final class HealthStore {
    private let store = HKHealthStore()
    private var observerQueries: [HKObserverQuery] = []

    var isAvailable: Bool {
        HKHealthStore.isHealthDataAvailable()
    }

    func requestAuthorization() async throws {
        let readTypes = Set([
            HKObjectType.quantityType(forIdentifier: .stepCount)!,
            HKObjectType.quantityType(forIdentifier: .activeEnergyBurned)!,
            HKObjectType.quantityType(forIdentifier: .restingHeartRate)!,
            HKObjectType.quantityType(forIdentifier: .heartRateVariabilitySDNN)!,
            HKObjectType.quantityType(forIdentifier: .bodyMass)!,
            HKObjectType.quantityType(forIdentifier: .vo2Max)!,
            HKObjectType.categoryType(forIdentifier: .sleepAnalysis)!,
            HKObjectType.workoutType()
        ])

        try await store.requestAuthorization(toShare: [], read: readTypes)
    }

    func enableBackgroundDelivery() {
        let identifiers: [HKQuantityTypeIdentifier] = [
            .stepCount,
            .activeEnergyBurned,
            .restingHeartRate,
            .heartRateVariabilitySDNN,
            .bodyMass,
            .vo2Max
        ]

        identifiers.compactMap { HKObjectType.quantityType(forIdentifier: $0) }.forEach { type in
            store.enableBackgroundDelivery(for: type, frequency: .immediate) { _, _ in }
        }

        if let sleepType = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) {
            store.enableBackgroundDelivery(for: sleepType, frequency: .immediate) { _, _ in }
        }

        store.enableBackgroundDelivery(for: HKObjectType.workoutType(), frequency: .immediate) { _, _ in }
    }

    func startObservingBackgroundChanges(onChange: @escaping @Sendable () async -> Void) {
        observerQueries.forEach { store.stop($0) }
        observerQueries.removeAll()

        let types: [HKSampleType] = [
            HKObjectType.quantityType(forIdentifier: .stepCount),
            HKObjectType.quantityType(forIdentifier: .activeEnergyBurned),
            HKObjectType.quantityType(forIdentifier: .restingHeartRate),
            HKObjectType.quantityType(forIdentifier: .heartRateVariabilitySDNN),
            HKObjectType.quantityType(forIdentifier: .bodyMass),
            HKObjectType.quantityType(forIdentifier: .vo2Max),
            HKObjectType.categoryType(forIdentifier: .sleepAnalysis),
            HKObjectType.workoutType()
        ].compactMap { $0 }

        for type in types {
            let query = HKObserverQuery(sampleType: type, predicate: nil) { _, completionHandler, error in
                if let error {
                    print("Health observer error for \(type): \(error.localizedDescription)")
                }

                Task {
                    await onChange()
                    completionHandler()
                }
            }
            observerQueries.append(query)
            store.execute(query)
        }
    }

    func fetchTodaySummary() async throws -> DailyHealthSummary {
        let now = Date()
        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: now)
        let predicate = HKQuery.predicateForSamples(withStart: startOfDay, end: now)

        return DailyHealthSummary(
            date: now,
            steps: await swallowNil { try await sumQuantity(.stepCount, unit: .count(), predicate: predicate) },
            activeKcal: await swallowNil { try await sumQuantity(.activeEnergyBurned, unit: .kilocalorie(), predicate: predicate) },
            restingHR: await swallowNil { try await averageQuantity(.restingHeartRate, unit: HKUnit.count().unitDivided(by: .minute()), predicate: predicate) },
            hrv: await swallowNil { try await averageQuantity(.heartRateVariabilitySDNN, unit: .secondUnit(with: .milli), predicate: predicate) },
            sleepHours: await swallowNil { try await sleepHours(predicate: predicate) },
            bodyMassKg: await swallowNil { try await latestQuantity(.bodyMass, unit: .gramUnit(with: .kilo)) },
            vo2max: await swallowNil { try await latestQuantity(.vo2Max, unit: HKUnit(from: "mL/kg*min")) },
            workouts: await swallowArray { try await todayWorkouts(predicate: predicate) }
        )
    }

    private func swallowNil<T>(_ operation: () async throws -> T?) async -> T? {
        do {
            return try await operation()
        } catch {
            return nil
        }
    }

    private func swallowArray<T>(_ operation: () async throws -> [T]) async -> [T] {
        do {
            return try await operation()
        } catch {
            return []
        }
    }

    private func sumQuantity(_ identifier: HKQuantityTypeIdentifier, unit: HKUnit, predicate: NSPredicate) async throws -> Double? {
        guard let type = HKObjectType.quantityType(forIdentifier: identifier) else { return nil }
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKStatisticsQuery(quantityType: type, quantitySamplePredicate: predicate, options: .cumulativeSum) { _, result, error in
                if let error { continuation.resume(throwing: error); return }
                let value = result?.sumQuantity()?.doubleValue(for: unit)
                continuation.resume(returning: value)
            }
            store.execute(query)
        }
    }

    private func averageQuantity(_ identifier: HKQuantityTypeIdentifier, unit: HKUnit, predicate: NSPredicate) async throws -> Double? {
        guard let type = HKObjectType.quantityType(forIdentifier: identifier) else { return nil }
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKStatisticsQuery(quantityType: type, quantitySamplePredicate: predicate, options: .discreteAverage) { _, result, error in
                if let error { continuation.resume(throwing: error); return }
                let value = result?.averageQuantity()?.doubleValue(for: unit)
                continuation.resume(returning: value)
            }
            store.execute(query)
        }
    }

    private func latestQuantity(_ identifier: HKQuantityTypeIdentifier, unit: HKUnit) async throws -> Double? {
        guard let type = HKObjectType.quantityType(forIdentifier: identifier) else { return nil }
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: type, predicate: nil, limit: 1, sortDescriptors: [sort]) { _, samples, error in
                if let error { continuation.resume(throwing: error); return }
                let sample = samples?.first as? HKQuantitySample
                continuation.resume(returning: sample?.quantity.doubleValue(for: unit))
            }
            store.execute(query)
        }
    }

    private func sleepHours(predicate: NSPredicate) async throws -> Double? {
        guard let type = HKObjectType.categoryType(forIdentifier: .sleepAnalysis) else { return nil }
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: type, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, samples, error in
                if let error { continuation.resume(throwing: error); return }
                let total = (samples as? [HKCategorySample] ?? [])
                    .filter { sample in
                        sample.value == HKCategoryValueSleepAnalysis.asleep.rawValue ||
                        sample.value == HKCategoryValueSleepAnalysis.asleepCore.rawValue ||
                        sample.value == HKCategoryValueSleepAnalysis.asleepDeep.rawValue ||
                        sample.value == HKCategoryValueSleepAnalysis.asleepREM.rawValue
                    }
                    .reduce(0.0) { partial, sample in
                        partial + sample.endDate.timeIntervalSince(sample.startDate)
                    }
                continuation.resume(returning: total > 0 ? total / 3600.0 : nil)
            }
            store.execute(query)
        }
    }

    private func todayWorkouts(predicate: NSPredicate) async throws -> [WorkoutPayload] {
        let sort = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: false)
        return try await withCheckedThrowingContinuation { continuation in
            let query = HKSampleQuery(sampleType: HKObjectType.workoutType(), predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: [sort]) { _, samples, error in
                if let error { continuation.resume(throwing: error); return }
                let workouts = (samples as? [HKWorkout] ?? []).map { workout in
                    WorkoutPayload(
                        type: workout.workoutActivityType.name,
                        start: ISO8601DateFormatter().string(from: workout.startDate),
                        durationMin: workout.duration / 60.0,
                        distanceKm: workout.totalDistance?.doubleValue(for: .meterUnit(with: .kilo))
                    )
                }
                continuation.resume(returning: workouts)
            }
            store.execute(query)
        }
    }
}

private extension HKWorkoutActivityType {
    var name: String {
        switch self {
        case .running: return "Running"
        case .walking: return "Walking"
        case .cycling: return "Cycling"
        case .traditionalStrengthTraining: return "Strength Training"
        default: return String(describing: self)
        }
    }
}
