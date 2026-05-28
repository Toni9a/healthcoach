from __future__ import annotations

import json
import socket
from datetime import date
from http import HTTPStatus
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from backend_store import (
    DB_FILE,
    LIVE_FILE,
    SITE_DIR,
    build_context,
    get_dashboard_snapshot,
    get_latest_live_sync,
    get_live_sync_history,
    get_plan_schedule,
    get_plan_workout,
    get_recent_runs,
    init_db,
    rebuild_from_source,
    save_live_sync,
    seed_from_current_files,
)


def local_ip() -> str:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return "127.0.0.1"


app = Flask(__name__, static_folder=str(SITE_DIR), static_url_path="")


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/api/live-health", methods=["GET", "POST", "OPTIONS"])
@app.route("/api/health/live", methods=["GET", "POST", "OPTIONS"])
def live_health():
    if request.method == "OPTIONS":
        return ("", HTTPStatus.NO_CONTENT)

    if request.method == "GET":
        payload = get_latest_live_sync() or {
            "last_sync_utc": None,
            "metrics": {},
            "notes": "No live Apple Health sync received yet.",
        }
        return jsonify(payload)

    incoming = request.get_json(silent=True)
    if not isinstance(incoming, dict):
        return jsonify({"ok": False, "error": "Expected JSON object"}), HTTPStatus.BAD_REQUEST

    stored = save_live_sync(incoming)
    return jsonify(
        {
            "ok": True,
            "stored": str(LIVE_FILE),
            "database": str(DB_FILE),
            "last_sync_utc": stored["last_sync_utc"],
        }
    )


@app.route("/api/status")
def api_status():
    latest = get_latest_live_sync()
    snapshot = get_dashboard_snapshot()
    return jsonify(
        {
            "ok": True,
            "site_dir": str(SITE_DIR),
            "database": str(DB_FILE),
            "live_file": str(LIVE_FILE),
            "suggested_url": f"http://{local_ip()}:8765",
            "last_sync_utc": None if latest is None else latest.get("last_sync_utc"),
            "dashboard_generated_at": None
            if snapshot is None
            else snapshot.get("meta", {}).get("generated_at"),
            "analysis_window": None
            if snapshot is None
            else snapshot.get("meta", {}).get("analysis_window"),
        }
    )


@app.route("/api/dashboard")
def api_dashboard():
    snapshot = get_dashboard_snapshot()
    if snapshot is None:
        return jsonify({"ok": False, "error": "No dashboard snapshot loaded"}), HTTPStatus.NOT_FOUND
    return jsonify(snapshot)


@app.route("/api/context")
def api_context():
    for_date = request.args.get("date") or date.today().isoformat()
    return jsonify(build_context(for_date))


@app.route("/api/plan/schedule")
def api_plan_schedule():
    return jsonify(get_plan_schedule())


@app.route("/api/plan/workout")
@app.route("/api/plan/today")
def api_plan_workout():
    for_date = request.args.get("date") or date.today().isoformat()
    workout = get_plan_workout(for_date)
    if workout is None:
        return jsonify({"ok": False, "date": for_date, "error": "No workout found"}), HTTPStatus.NOT_FOUND
    return jsonify({"ok": True, "workout": workout})


@app.route("/api/runs/recent")
def api_runs_recent():
    limit = request.args.get("limit", default=20, type=int)
    limit = min(max(limit, 1), 100)
    return jsonify(get_recent_runs(limit=limit))


@app.route("/api/health/food-focus")
def api_food_focus():
    snapshot = get_dashboard_snapshot() or {}
    return jsonify(snapshot.get("food_focus", {}))


@app.route("/api/health/history")
def api_health_history():
    limit = request.args.get("limit", default=20, type=int)
    limit = min(max(limit, 1), 100)
    return jsonify(get_live_sync_history(limit=limit))


@app.route("/api/admin/rebuild", methods=["POST"])
def api_rebuild():
    result = rebuild_from_source()
    return jsonify({"ok": True, **result})


@app.route("/")
def root():
    return send_from_directory(SITE_DIR, "index.html")


@app.route("/<path:filename>")
def site_files(filename: str):
    file_path = SITE_DIR / filename
    if file_path.exists() and file_path.is_file():
        return send_from_directory(SITE_DIR, filename)
    return send_from_directory(SITE_DIR, "index.html")


def bootstrap() -> None:
    init_db()
    seed_from_current_files()


if __name__ == "__main__":
    bootstrap()
    host = "0.0.0.0"
    port = 8765
    print(f"Serving site + backend at http://{local_ip()}:{port}")
    print("Apple Health sync endpoint: POST /api/live-health")
    print("Dashboard API: GET /api/dashboard")
    print("Plan API: GET /api/plan/workout?date=YYYY-MM-DD")
    app.run(host=host, port=port, threaded=True)
