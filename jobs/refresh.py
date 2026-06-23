"""Refresh pipeline: scrape CPD site, download PDFs, parse schedules, update DB."""

import sys
import tempfile
from datetime import datetime, timezone

import httpx

from app.models import (
    get_db, init_db, upsert_facility, update_facility_schedule,
    replace_swim_slots, get_facility_etag,
)
from app.parser import parse_pdf
from app.scraper import fetch_all


def refresh(db_path=None):
    conn = get_db(db_path)
    init_db(conn)

    print("Fetching facility listings...")
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        facilities = fetch_all(client)
        print(f"Found {len(facilities)} facilities")

        success = 0
        skipped = 0
        failed = 0

        for fac in facilities:
            facility_id = upsert_facility(conn, fac)
            conn.commit()

            pdf_url = fac.get("schedule_pdf_url")
            if not pdf_url:
                print(f"  {fac['name']}: no PDF URL")
                failed += 1
                continue

            # ETag-based conditional fetch
            stored_etag = get_facility_etag(conn, fac["slug"])
            headers = {}
            if stored_etag:
                headers["If-None-Match"] = stored_etag

            try:
                resp = client.get(pdf_url, headers=headers)
            except httpx.HTTPError as e:
                print(f"  {fac['name']}: HTTP error: {e}")
                failed += 1
                continue

            if resp.status_code == 304:
                print(f"  {fac['name']}: not modified (ETag match)")
                skipped += 1
                continue

            if resp.status_code != 200:
                print(f"  {fac['name']}: HTTP {resp.status_code}")
                failed += 1
                continue

            new_etag = resp.headers.get("ETag")

            # Write PDF to temp file and parse
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
                tmp.write(resp.content)
                tmp.flush()
                try:
                    result = parse_pdf(tmp.name)
                except Exception as e:
                    print(f"  {fac['name']}: parse error: {e}")
                    failed += 1
                    continue

            now = datetime.now(timezone.utc).isoformat()
            update_facility_schedule(
                conn, facility_id, new_etag,
                result.get("date_start"), result.get("date_end"), now,
            )
            replace_swim_slots(conn, facility_id, result["slots"])
            conn.commit()

            print(f"  {fac['name']}: {len(result['slots'])} slots")
            success += 1

    print(f"\nDone: {success} parsed, {skipped} unchanged, {failed} failed")
    conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else None
    refresh(db_path)
