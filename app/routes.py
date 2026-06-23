"""Flask routes for API and page serving."""

import os

from flask import Blueprint, current_app, jsonify, render_template, request, Response, send_from_directory

from .calendar_utils import make_ics, google_calendar_url
from .models import get_db, get_all_data

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/sw.js")
def service_worker():
    resp = send_from_directory(current_app.static_folder, "sw.js")
    resp.headers["Service-Worker-Allowed"] = "/"
    return resp


@bp.route("/api/data")
def api_data():
    conn = get_db()
    try:
        data = get_all_data(conn)
        return jsonify(data)
    finally:
        conn.close()


@bp.route("/api/calendar/ics")
def api_calendar_ics():
    facility_id = request.args.get("facility_id", type=int)
    day = request.args.get("day", type=int)
    start = request.args.get("start")
    swim_type = request.args.get("type")

    if not all([facility_id is not None, day is not None, start, swim_type]):
        return jsonify({"error": "Missing parameters"}), 400

    conn = get_db()
    try:
        fac = conn.execute(
            "SELECT name, address, schedule_date_start, schedule_date_end FROM facilities WHERE id = ?",
            (facility_id,)
        ).fetchone()
        if not fac:
            return jsonify({"error": "Facility not found"}), 404

        slot = conn.execute(
            "SELECT end_time FROM swim_slots WHERE facility_id = ? AND day_of_week = ? AND start_time = ? AND swim_type = ?",
            (facility_id, day, start, swim_type)
        ).fetchone()
        if not slot:
            return jsonify({"error": "Slot not found"}), 404

        ics = make_ics(
            facility_name=fac["name"],
            swim_type=swim_type,
            day_of_week=day,
            start_time=start,
            end_time=slot["end_time"],
            date_start=fac["schedule_date_start"] or "2026-06-20",
            date_end=fac["schedule_date_end"] or "2026-08-02",
            address=fac["address"] or "",
        )
        return Response(
            ics,
            mimetype="text/calendar",
            headers={"Content-Disposition": f"attachment; filename=swim-{fac['name'].lower().replace(' ', '-')}.ics"},
        )
    finally:
        conn.close()


@bp.route("/api/calendar/google")
def api_calendar_google():
    facility_id = request.args.get("facility_id", type=int)
    day = request.args.get("day", type=int)
    start = request.args.get("start")
    swim_type = request.args.get("type")

    if not all([facility_id is not None, day is not None, start, swim_type]):
        return jsonify({"error": "Missing parameters"}), 400

    conn = get_db()
    try:
        fac = conn.execute(
            "SELECT name, address, schedule_date_start, schedule_date_end FROM facilities WHERE id = ?",
            (facility_id,)
        ).fetchone()
        if not fac:
            return jsonify({"error": "Facility not found"}), 404

        slot = conn.execute(
            "SELECT end_time FROM swim_slots WHERE facility_id = ? AND day_of_week = ? AND start_time = ? AND swim_type = ?",
            (facility_id, day, start, swim_type)
        ).fetchone()
        if not slot:
            return jsonify({"error": "Slot not found"}), 404

        url = google_calendar_url(
            facility_name=fac["name"],
            swim_type=swim_type,
            day_of_week=day,
            start_time=start,
            end_time=slot["end_time"],
            date_start=fac["schedule_date_start"] or "2026-06-20",
            date_end=fac["schedule_date_end"] or "2026-08-02",
            address=fac["address"] or "",
        )
        return jsonify({"url": url})
    finally:
        conn.close()


@bp.route("/api/refresh", methods=["POST"])
def api_refresh():
    token = os.environ.get("SWIMCHI_REFRESH_TOKEN", "")
    if token and request.headers.get("Authorization") != f"Bearer {token}":
        return jsonify({"error": "Unauthorized"}), 401

    from jobs.refresh import refresh
    refresh()
    return jsonify({"status": "ok"})
