from __future__ import annotations

import csv
import json
import os
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


SITE_DIR = Path(__file__).resolve().parent
DATA_ROOT = Path(os.environ.get("TONI_DATA_DIR", str(SITE_DIR)))
DB_FILE = Path(os.environ.get("TONI_DB_FILE", str(DATA_ROOT / "toni_backend.sqlite3")))
LIVE_FILE = Path(os.environ.get("TONI_LIVE_FILE", str(DATA_ROOT / "live-health.json")))
DATA_JS = Path(os.environ.get("TONI_DASHBOARD_DATA_JS", str(SITE_DIR / "data.js")))
PLAN_CSV = Path(os.environ.get("TONI_PLAN_CSV", str(SITE_DIR / "plan_schedule.csv")))


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_data_dirs() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    LIVE_FILE.parent.mkdir(parents=True, exist_ok=True)


def get_conn() -> sqlite3.Connection:
    ensure_data_dirs()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dashboard_snapshots (
                key TEXT PRIMARY KEY,
                generated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS plan_workouts (
                workout_date TEXT PRIMARY KEY,
                day_name TEXT,
                category TEXT,
                duration TEXT,
                details TEXT,
                target_pace TEXT,
                target_hr TEXT,
                notes TEXT
            );

            CREATE TABLE IF NOT EXISTS recent_runs (
                run_date TEXT NOT NULL,
                name TEXT,
                distance_km REAL,
                pace_min_km REAL,
                avg_hr REAL,
                class TEXT,
                drift REAL
            );

            CREATE TABLE IF NOT EXISTS live_health_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            """
        )


def set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value) VALUES(?, ?)
            ON CONFLICT(key) DO UPDATE SET value=excluded.value
            """,
            (key, value),
        )


def get_setting(key: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
    return None if row is None else row["value"]


def parse_data_js_payload(text: str) -> dict[str, Any]:
    return json.loads(text.split("=", 1)[1].rsplit(";", 1)[0])


def load_data_js_payload() -> dict[str, Any] | None:
    if not DATA_JS.exists():
        return None
    try:
        return parse_data_js_payload(DATA_JS.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_dashboard_snapshot(payload: dict[str, Any]) -> None:
    generated_at = payload.get("meta", {}).get("generated_at") or utc_now()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO dashboard_snapshots(key, generated_at, payload_json)
            VALUES(?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              generated_at=excluded.generated_at,
              payload_json=excluded.payload_json
            """,
            ("latest", generated_at, json.dumps(payload)),
        )


def get_dashboard_snapshot() -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT payload_json FROM dashboard_snapshots WHERE key = 'latest'"
        ).fetchone()
    return None if row is None else json.loads(row["payload_json"])


def save_plan_schedule_from_csv() -> int:
    if not PLAN_CSV.exists():
        return 0

    with PLAN_CSV.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    with get_conn() as conn:
        conn.execute("DELETE FROM plan_workouts")
        conn.executemany(
            """
            INSERT INTO plan_workouts(
                workout_date, day_name, category, duration, details, target_pace, target_hr, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("date"),
                    row.get("day"),
                    row.get("category"),
                    row.get("duration"),
                    row.get("details"),
                    row.get("target_pace"),
                    row.get("target_hr"),
                    row.get("notes"),
                )
                for row in rows
            ],
        )
    return len(rows)


def get_plan_schedule() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT workout_date AS date, day_name AS day, category, duration, details,
                   target_pace, target_hr, notes
            FROM plan_workouts
            ORDER BY workout_date
            """
        ).fetchall()
    return [dict(row) for row in rows]


def get_plan_workout(for_date: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT workout_date AS date, day_name AS day, category, duration, details,
                   target_pace, target_hr, notes
            FROM plan_workouts
            WHERE workout_date = ?
            """,
            (for_date,),
        ).fetchone()
    return None if row is None else dict(row)


def save_recent_runs(rows: list[dict[str, Any]]) -> int:
    with get_conn() as conn:
        conn.execute("DELETE FROM recent_runs")
        conn.executemany(
            """
            INSERT INTO recent_runs(run_date, name, distance_km, pace_min_km, avg_hr, class, drift)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row.get("date"),
                    row.get("name"),
                    row.get("distance_km"),
                    row.get("pace_min_km"),
                    row.get("avg_hr"),
                    row.get("class"),
                    row.get("drift"),
                )
                for row in rows
            ],
        )
    return len(rows)


def get_recent_runs(limit: int = 20) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT run_date AS date, name, distance_km, pace_min_km, avg_hr, class, drift
            FROM recent_runs
            ORDER BY run_date DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def normalize_live_payload(payload: dict[str, Any]) -> dict[str, Any]:
    existing = get_latest_live_sync() or {}
    metrics = existing.get("metrics", {})
    metrics.update(payload.get("metrics", {}))

    top = {}
    for key in ["date", "source", "workouts", "notes"]:
        if key in payload:
            top[key] = payload[key]
        elif key in existing:
            top[key] = existing[key]

    return {
        "last_sync_utc": utc_now(),
        "metrics": metrics,
        **top,
    }


def save_live_sync(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_live_payload(payload)
    LIVE_FILE.write_text(json.dumps(normalized, indent=2), encoding="utf-8")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO live_health_events(received_at, payload_json) VALUES(?, ?)",
            (normalized["last_sync_utc"], json.dumps(normalized)),
        )
    return normalized


def seed_live_sync_from_file() -> None:
    if not LIVE_FILE.exists():
        return
    try:
        payload = json.loads(LIVE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) AS c FROM live_health_events").fetchone()["c"]
        if count == 0:
            conn.execute(
                "INSERT INTO live_health_events(received_at, payload_json) VALUES(?, ?)",
                (payload.get("last_sync_utc") or utc_now(), json.dumps(payload)),
            )


def get_latest_live_sync() -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT payload_json
            FROM live_health_events
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()
    return None if row is None else json.loads(row["payload_json"])


def get_live_sync_history(limit: int = 20) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT payload_json
            FROM live_health_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


def seed_from_current_files() -> dict[str, int]:
    counts = {"plan_workouts": 0, "recent_runs": 0}
    payload = load_data_js_payload()
    if payload:
        save_dashboard_snapshot(payload)
        counts["recent_runs"] = save_recent_runs(
            payload.get("run_summary", {}).get("recent_runs", [])
        )
    counts["plan_workouts"] = save_plan_schedule_from_csv()
    seed_live_sync_from_file()
    return counts


def rebuild_from_source() -> dict[str, Any]:
    import importlib.util

    builder_path = SITE_DIR / "build_dashboard_data.py"
    spec = importlib.util.spec_from_file_location("dashboard_builder", builder_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load build_dashboard_data.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = module.build_dashboard_data()
    DATA_JS.write_text(
        "window.DASHBOARD_DATA = " + json.dumps(payload, indent=2) + ";\n",
        encoding="utf-8",
    )
    save_dashboard_snapshot(payload)
    recent_runs_count = save_recent_runs(
        payload.get("run_summary", {}).get("recent_runs", [])
    )
    plan_count = save_plan_schedule_from_csv()
    set_setting("last_rebuild_utc", utc_now())
    return {
        "dashboard_generated_at": payload.get("meta", {}).get("generated_at"),
        "recent_runs": recent_runs_count,
        "plan_workouts": plan_count,
    }


def build_context(for_date: str | None = None) -> dict[str, Any]:
    snapshot = get_dashboard_snapshot() or {}
    workout_date = for_date or date.today().isoformat()
    return {
        "today": workout_date,
        "plan_workout": get_plan_workout(workout_date),
        "live_health": get_latest_live_sync(),
        "recent_runs": get_recent_runs(limit=10),
        "headline": snapshot.get("headline"),
        "numbers": snapshot.get("numbers"),
        "food_focus": snapshot.get("food_focus"),
        "analysis_window": snapshot.get("meta", {}).get("analysis_window"),
    }
