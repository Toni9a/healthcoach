# Health Sync

This site now runs on a small Flask backend so your iPhone can send Apple Health data into it automatically and the dashboard can read the processed data from the same server.

## What this does

- serves the dashboard locally from your Mac
- serves the dashboard APIs used by the site
- accepts `POST` requests from your iPhone at `/api/live-health`
- stores the latest sync in `live-health.json`
- stores backend data in `toni_backend.sqlite3`
- exposes `GET /api/live-health` so the dashboard can display the latest sync
- exposes dashboard, plan, context, and food-summary APIs

## Start the bridge

Run:

```bash
python3 /Users/toni/strav/site/health_bridge_server.py
```

It will print a LAN URL like:

```text
http://192.168.1.23:8765
```

Open that URL on your Mac or iPhone instead of using `file:///...`.

The site reads live data from:

- `GET /api/dashboard`
- `GET /api/context`
- `GET /api/plan/workout?date=YYYY-MM-DD`
- `GET /api/health/food-focus`

## Expected payload

Send a JSON object like this:

```json
{
  "date": "2026-05-14",
  "source": "Apple Health Shortcut",
  "metrics": {
    "steps": 14820,
    "active_kcal": 824,
    "resting_hr": 52,
    "hrv": 68.4,
    "sleep_hours": 7.6,
    "body_mass_kg": 90.7,
    "vo2max": 46.9
  },
  "workouts": [
    {
      "type": "Running",
      "start": "2026-05-14T18:30:00+01:00",
      "duration_min": 25,
      "distance_km": 3.2
    }
  ]
}
```

The backend writes this into `live-health.json` and stores sync history in `toni_backend.sqlite3`.

## Useful API routes

- `GET /api/status`
- `GET /api/dashboard`
- `GET /api/context`
- `GET /api/plan/workout?date=YYYY-MM-DD`
- `GET /api/plan/schedule`
- `GET /api/health/food-focus`
- `GET /api/runs/recent`
- `GET /api/health/history`
- `POST /api/admin/rebuild`

## Free sync options

### Option 1: iPhone Shortcuts -> this backend

Free, but slightly manual to set up.

Suggested Shortcut flow:

1. Read Health metrics for today.
2. Build a dictionary matching the JSON shape above.
3. Use `Get Contents of URL`.
4. Method: `POST`
5. URL: `http://YOUR-MAC-IP:8765/api/live-health`
6. Request body: JSON
7. Save as a personal automation to run daily.

### Option 2: Heartbridge

Free and open source:

- GitHub: <https://github.com/mm/heartbridge>

Heartbridge uses Shortcuts plus a Python HTTP endpoint on your computer.

### Option 3: Health Auto Export

Easy, but automatic background export is not fully free:

- App Store: <https://apps.apple.com/us/app/health-auto-export-json-csv/id1115567069>
- Docs: <https://github.com/Lybron/health-auto-export>

### Option 4: Health Exporter & Shortcuts

Cheap, not free:

- App Store: <https://apps.apple.com/us/app/health-exporter-shortcuts/id6759006922>

## Notes

- Apple Health data cannot be read directly by a normal hosted website.
- The iPhone side must have HealthKit access.
- If you later want Strava too, use Apple Health for recovery metrics and the latest Strava export for run metadata.
