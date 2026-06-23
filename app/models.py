"""SQLite database schema and query helpers."""

import os
import sqlite3
from pathlib import Path

DB_PATH = os.environ.get("SWIMCHI_DB", str(Path(__file__).parent.parent / "swimchi.db"))


def get_db(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = str(path or DB_PATH)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS facilities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            address TEXT,
            lat REAL,
            lon REAL,
            schedule_pdf_url TEXT,
            schedule_pdf_etag TEXT,
            schedule_date_start TEXT,
            schedule_date_end TEXT,
            last_scraped_at TEXT
        );

        CREATE TABLE IF NOT EXISTS swim_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_id INTEGER NOT NULL REFERENCES facilities(id),
            day_of_week INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            swim_type TEXT NOT NULL,
            UNIQUE(facility_id, day_of_week, start_time, swim_type)
        );
    """)


def upsert_facility(conn: sqlite3.Connection, facility: dict) -> int:
    """Insert or update a facility. Returns the facility ID."""
    conn.execute("""
        INSERT INTO facilities (slug, name, address, lat, lon, schedule_pdf_url)
        VALUES (:slug, :name, :address, :lat, :lon, :schedule_pdf_url)
        ON CONFLICT(slug) DO UPDATE SET
            name = excluded.name,
            address = excluded.address,
            lat = COALESCE(excluded.lat, facilities.lat),
            lon = COALESCE(excluded.lon, facilities.lon),
            schedule_pdf_url = excluded.schedule_pdf_url
    """, facility)
    row = conn.execute(
        "SELECT id FROM facilities WHERE slug = ?", (facility["slug"],)
    ).fetchone()
    return row["id"]


def update_facility_schedule(conn: sqlite3.Connection, facility_id: int,
                              etag: str | None, date_start: str | None,
                              date_end: str | None, scraped_at: str):
    conn.execute("""
        UPDATE facilities SET
            schedule_pdf_etag = ?,
            schedule_date_start = ?,
            schedule_date_end = ?,
            last_scraped_at = ?
        WHERE id = ?
    """, (etag, date_start, date_end, scraped_at, facility_id))


def replace_swim_slots(conn: sqlite3.Connection, facility_id: int, slots: list[dict]):
    """Delete existing slots for a facility and insert new ones."""
    conn.execute("DELETE FROM swim_slots WHERE facility_id = ?", (facility_id,))
    for slot in slots:
        conn.execute("""
            INSERT INTO swim_slots (facility_id, day_of_week, start_time, end_time, swim_type)
            VALUES (?, ?, ?, ?, ?)
        """, (facility_id, slot["day_of_week"], slot["start_time"],
              slot["end_time"], slot["swim_type"]))


def get_facility_etag(conn: sqlite3.Connection, slug: str) -> str | None:
    row = conn.execute(
        "SELECT schedule_pdf_etag FROM facilities WHERE slug = ?", (slug,)
    ).fetchone()
    return row["schedule_pdf_etag"] if row else None


def get_all_data(conn: sqlite3.Connection) -> dict:
    """Get all facilities and swim slots for the API response."""
    facilities = []
    for row in conn.execute("""
        SELECT id, slug, name, address, lat, lon,
               schedule_date_start, schedule_date_end
        FROM facilities ORDER BY name
    """):
        facilities.append(dict(row))

    slots = []
    for row in conn.execute("""
        SELECT facility_id, day_of_week, start_time, end_time, swim_type
        FROM swim_slots ORDER BY facility_id, day_of_week, start_time
    """):
        slots.append(dict(row))

    swim_types = sorted({s["swim_type"] for s in slots})

    return {"facilities": facilities, "slots": slots, "swim_types": swim_types}
