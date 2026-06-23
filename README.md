# SwimChi

A web app that scrapes all 82 Chicago Park District pool schedule PDFs, parses them into structured data, and presents a filterable UI for finding swim times.

The Chicago Park District publishes pool schedules as individual PDFs — one per pool — buried across paginated listings on their website. SwimChi pulls them all together into a single searchable interface with distance filtering, favorites, and calendar integration.

## How it works

### Data pipeline

1. **Scrape** the CPD facilities API to get pool names, addresses, GPS coordinates, and PDF URLs. The API serves paginated HTML via JSON; the list view has names/addresses/PDFs and the map view (page 0 only) has lat/lon for all 82 pools.

2. **Download** each pool's schedule PDF. ETags are stored so subsequent runs skip unchanged files.

3. **Parse** the PDF tables with pdfplumber. Each PDF has a 9-column table (TIME, MON–FRI, TIME, SAT, SUN) with varying layouts — some use shared time suffixes (`9-11am`), some use individual markers (`11:00a-12:00p`), and some split times across rows (`11:00AM -` / `12:00PM`). The parser handles all three.

4. **Store** everything in SQLite (WAL mode for concurrent reads during writes). ~2800 swim slots across ~70 facilities with schedule data.

### Web app

Flask serves a single HTML page that fetches all data as JSON on load (~50-80KB). All filtering happens client-side:

- **Swim type** — Open Swim, Lap Swim, Parent & Child, Day Camp, etc.
- **Day of week**
- **Pool** — dropdown of all facilities
- **Distance** — uses browser geolocation + Haversine formula
- **Favorites** — star pools to filter by them later; saved in cookies

Each row has links to download an `.ics` file or open Google Calendar with the recurring event pre-filled.

## Project structure

```
app/
  __init__.py          # Flask app factory
  models.py            # SQLite schema + queries
  scraper.py           # CPD API scraper
  parser.py            # PDF table extraction
  calendar_utils.py    # .ics + Google Calendar URL generation
  routes.py            # Flask routes
  templates/
    index.html
  static/
    app.js             # Client-side filtering and rendering
    app.css
    favicon.ico        # Chicago skyline + waves
    *.png              # App icons (16, 32, 180, 192, 512)
    site.webmanifest
jobs/
  refresh.py           # CLI: scrape + parse + update DB
tests/
  test_parser.py
  test_scraper.py
  fixtures/            # Sample PDF + HTML for tests
```

## Local development

```sh
pip install -r requirements.txt
python -m jobs.refresh        # populate the database (~2 min)
flask --app app run           # http://localhost:5000
```

Run tests:

```sh
pip install pytest
pytest
```

## Deploy with Docker

```sh
docker compose up --build
```

On first launch, the entrypoint automatically runs a full data refresh (~2 min) before starting the server. Subsequent restarts skip this if the database already exists. A daily cron job at 6am keeps the data current.

To protect the manual refresh endpoint, set a token:

```sh
SWIMCHI_REFRESH_TOKEN=secret docker compose up --build
```

Then trigger a refresh with:

```sh
curl -X POST -H "Authorization: Bearer secret" http://localhost:8000/api/refresh
```

## API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Main page |
| `/api/data` | GET | All facilities, swim slots, and swim types as JSON |
| `/api/calendar/ics?facility_id=&day=&start=&type=` | GET | Download .ics file for a recurring swim slot |
| `/api/calendar/google?facility_id=&day=&start=&type=` | GET | Get Google Calendar event creation URL |
| `/api/refresh` | POST | Trigger data refresh (token-protected) |
