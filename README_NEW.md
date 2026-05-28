# Toni Fitness Dashboard

This repo is the working fitness system for Toni. It combines:

- Apple Health exports
- Strava exports
- a local Flask backend
- a SwiftUI iPhone sync app
- a browser dashboard for summary + plan views

## Current State

The current setup is working end-to-end in a local/manual-sync form, with the phone app now also showing the dashboard and plan in-app.

- The dashboard reads live data from the backend.
- The iPhone app syncs Apple Health data to the backend.
- The iPhone app has Sync, Dashboard, and Plan tabs.
- HealthKit updates can trigger background sync attempts.
- The backend stores live syncs in SQLite and serves dashboard APIs.
- The plan page reads the training schedule from the backend too.

## Main Files

- Dashboard summary: `/Users/toni/strav/site/index.html`
- Plan page: `/Users/toni/strav/site/plan.html`
- Backend server: `/Users/toni/strav/site/health_bridge_server.py`
- Backend store: `/Users/toni/strav/site/backend_store.py`
- Backend database: `/Users/toni/strav/site/toni_backend.sqlite3`
- Dashboard snapshot builder: `/Users/toni/strav/site/build_dashboard_data.py`
- Dashboard script: `/Users/toni/strav/site/script.js`
- Plan script: `/Users/toni/strav/site/plan-script.js`
- Plan CSV: `/Users/toni/strav/site/plan_schedule.csv`
- iPhone app project: `/Users/toni/strav/companion-app/ToniHealthSyncCompanion.xcodeproj`
- Hosted entrypoint: `/Users/toni/strav/app.py`
- Python deps: `/Users/toni/strav/requirements.txt`
- Render deploy file: `/Users/toni/strav/render.yaml`

## Fresh Data Sources

- Apple Health export: `/Users/toni/strav/MAY apple_health_export`
- Strava export: `/Users/toni/strav/export_56684747-2`

These are the current source exports used for analysis.

## How It Runs

### Start the backend

```bash
python3 /Users/toni/strav/site/health_bridge_server.py
```

### Rebuild the analysis snapshot from the source exports

```bash
python3 /Users/toni/strav/generate_splits_last_6_months.py
python3 /Users/toni/strav/site/build_dashboard_data.py
curl -X POST http://192.168.1.196:8765/api/admin/rebuild
```

### Open the dashboard

- Summary: `http://192.168.1.196:8765/index.html`
- Plan: `http://192.168.1.196:8765/plan.html`

### Hosted-ready files

The repo is now prepared for a simple Python web deploy:

- `app.py` exposes the Flask app cleanly for `gunicorn`
- `requirements.txt` lists the Python runtime deps
- `render.yaml` defines a hosted web service plus persistent disk
- backend paths can be overridden with:
  - `TONI_DATA_DIR`
  - `TONI_DB_FILE`
  - `TONI_LIVE_FILE`

## Backend API

- `GET /api/status`
- `GET /api/dashboard`
- `GET /api/context`
- `GET /api/live-health`
- `GET /api/plan/schedule`
- `GET /api/plan/workout?date=YYYY-MM-DD`
- `GET /api/health/food-focus`
- `GET /api/runs/recent`
- `GET /api/health/history`
- `POST /api/live-health`
- `POST /api/admin/rebuild`

## iPhone App Flow

The app syncs Apple Health into the backend and can also display the dashboard locally.

1. Open the Xcode project.
2. Allow HealthKit access.
3. Set the backend URL to:

```text
http://192.168.1.196:8765/api/live-health
```

4. Tap `Load Today's Data`.
5. Tap `Sync Now`.
6. Use the `Dashboard` and `Plan` tabs to view the backend pages inside the app.

## Data Windows

Current generated dashboard windows:

- Runs: `2026-03-26` to `2026-05-24`
- Health: `2026-01-28` to `2026-05-27`
- Food: `2026-05-07` to `2026-05-27`

## What The Dashboard Currently Shows

- current 5K estimate
- recent run intensity distribution
- plan vs actual execution notes
- Apple Health summary
- calories and macros from recent food logs
- live sync from the iPhone app
- the current training plan and day-by-day schedule

## Known Limits

- Background sync is better now, but still opportunistic rather than guaranteed.
- Strava is used from export files, not a live API feed yet.
- The live summary section will probably need another UI pass later.
- The backend is still not actually online yet because no hosting account has been connected from this session.

## Good Starting Point For A New Chat

If you open a fresh chat, the fastest context to mention is:

- this repo is the Toni fitness dashboard/backend/app system
- the active exports are in `MAY apple_health_export` and `export_56684747-2`
- the backend is `site/health_bridge_server.py`
- the dashboard reads from `/api/dashboard` and `/api/context`
- the phone app posts to `/api/live-health`
