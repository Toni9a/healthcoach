# Toni Health Sync Companion

This is a SwiftUI iPhone companion app for syncing Apple Health data into the dashboard backend and viewing the dashboard inside the app.

## What it does

- requests HealthKit read access for:
  - steps
  - active energy
  - resting heart rate
  - HRV
  - sleep
  - body mass
  - VO2max
  - workouts
- builds a daily summary payload
- posts that payload to your dashboard backend at:
  - `http://YOUR-MAC-IP:8765/api/live-health`
  - or a hosted HTTPS endpoint later
- shows the backend dashboard and plan pages in app tabs
- uses HealthKit observers and background fetch to try background syncs when Health data changes

## Project

Open:

```text
/Users/toni/strav/companion-app/ToniHealthSyncCompanion.xcodeproj
```

## To run this on your iPhone

You need:

1. full Xcode on your Mac
2. your Apple ID signed into Xcode
3. an iPhone connected for local deployment

## No paid Apple Developer account?

You can still run this on **your own device** with a personal Apple ID in Xcode.

Important caveat:
- free personal signing is fine for private testing
- the app signing is temporary and usually needs refreshing periodically
- for background sync reliability and long-term use, a paid Apple Developer account is better

## How to use this project

1. Open `ToniHealthSyncCompanion.xcodeproj` in Xcode.
2. Select the `ToniHealthSyncCompanion` target.
3. In `Signing & Capabilities`, choose your personal team.
4. Change the bundle identifier if Xcode asks for a unique one.
5. Confirm these capabilities are enabled:
   - HealthKit
   - Background Modes
     - Background fetch
6. Plug in your iPhone and trust the Mac if prompted.
7. Choose your iPhone as the run destination.
8. Build and run.

If Xcode says the active developer directory is wrong, run this once in Terminal:

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
```

## App flow

- First launch:
  - enter backend URL
  - tap authorize
  - tap sync now
- Later:
  - the app can sync manually
  - observer queries and background fetch can trigger sync attempts in the background

The phone app is only one half of the setup. The Mac backend now also serves the dashboard and plan APIs that the site reads from:

- `GET /api/dashboard`
- `GET /api/context`
- `GET /api/plan/workout?date=YYYY-MM-DD`
- `GET /api/health/food-focus`

## Files

- `Sources/ToniHealthSyncCompanionApp.swift`
- `Sources/ContentView.swift`
- `Sources/HealthSyncViewModel.swift`
- `Sources/HealthStore.swift`
- `Sources/SyncService.swift`
- `Sources/Models.swift`
- `CONFIG.md`

## Current status

As of `2026-05-28`, this project is in a working sync-and-dashboard state:

- app installs and runs on iPhone
- HealthKit authorization works
- `Load Today's Data` works
- `Sync Now` posts to the local bridge successfully
- Dashboard and Plan tabs load the backend pages inside the app
- the Mac backend stores sync history in SQLite and serves the dashboard data live

The local dashboard side is documented in:

- `/Users/toni/strav/WORKING_STATE.md`
