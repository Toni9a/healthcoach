# Working State

Updated: 2026-05-28

## What is working

### Dashboard

- Summary page:
  - `/Users/toni/strav/site/index.html`
- Plan page:
  - `/Users/toni/strav/site/plan.html`
- Day-by-day training plan CSV:
  - `/Users/toni/strav/site/plan_schedule.csv`
- Live backend-driven dashboard:
  - summary reads `/api/dashboard`
  - context endpoint at `/api/context`
  - plan endpoint at `/api/plan/workout?date=YYYY-MM-DD`
  - food summary at `/api/health/food-focus`

### Local health sync bridge

- Server file:
  - `/Users/toni/strav/site/health_bridge_server.py`
- Backend database:
  - `/Users/toni/strav/site/toni_backend.sqlite3`
- Main backend code:
  - `/Users/toni/strav/site/backend_store.py`
- Start command:

```bash
python3 /Users/toni/strav/site/health_bridge_server.py
```

- Working local LAN URL example:

```text
http://192.168.1.196:8765
```

- Live health endpoint:

```text
http://192.168.1.196:8765/api/live-health
```

- Dashboard endpoint:

```text
http://192.168.1.196:8765/api/dashboard
```

- Other useful backend endpoints:

```text
http://192.168.1.196:8765/api/dashboard
http://192.168.1.196:8765/api/context
http://192.168.1.196:8765/api/plan/workout?date=2026-05-27
http://192.168.1.196:8765/api/health/food-focus
```

### iPhone app

- Xcode project:
  - `/Users/toni/strav/companion-app/ToniHealthSyncCompanion.xcodeproj`

- App can:
  - request HealthKit access
  - load today’s health summary
  - sync JSON to the backend endpoint
  - show Dashboard and Plan tabs in-app
  - try background sync when HealthKit updates arrive

## Verified current flow

1. Run the bridge server on the Mac.
2. Open the iPhone app.
3. Authorize Health access.
4. Set backend URL to:

```text
http://192.168.1.196:8765/api/live-health
```

5. Tap `Load Today's Data`
6. Tap `Sync Now`
7. Open the dashboard over HTTP, not `file:///`

Summary:

```text
http://192.168.1.196:8765/index.html
```

Plan:

```text
http://192.168.1.196:8765/plan.html
```

## Notes

- The summary page now reads from the backend and falls back to the snapshot if needed.
- The plan page reads schedule data from the backend too.
- The current live sync payload is stored at:
  - `/Users/toni/strav/site/live-health.json`
- Fresh baseline exports are now in use:
  - Apple Health: `/Users/toni/strav/MAY apple_health_export`
  - Strava: `/Users/toni/strav/export_56684747-2`
- Rebuild commands for the refreshed baseline:

```bash
python3 /Users/toni/strav/generate_splits_last_6_months.py
python3 /Users/toni/strav/site/build_dashboard_data.py
```

- Full backend rebuild from source:

```bash
curl -X POST http://192.168.1.196:8765/api/admin/rebuild
```

- Current generated dashboard window after refresh:
  - runs: `2026-03-26` to `2026-05-24`
  - health: `2026-01-28` to `2026-05-27`
  - food: `2026-05-07` to `2026-05-27`

## Known limitations

- The iPhone app still has a manual sync button, but it also attempts background sync when HealthKit changes arrive.
- The summary page live section is basic and will likely need redesign.
- Strava live sync is not connected as a separate live feed yet, but the backend already uses the latest Strava export.
