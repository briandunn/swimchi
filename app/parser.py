"""Parse Chicago Park District pool schedule PDFs into structured swim slots."""

import re

import pdfplumber

# Column indices in the 9-column table
COL_TIME_WD = 0  # Weekday time
COL_MON = 1
COL_TUE = 2
COL_WED = 3
COL_THU = 4
COL_FRI = 5
COL_TIME_WE = 6  # Weekend time
COL_SAT = 7
COL_SUN = 8

DAY_COLS = {
    0: COL_MON,  # Mon
    1: COL_TUE,  # Tue
    2: COL_WED,  # Wed
    3: COL_THU,  # Thu
    4: COL_FRI,  # Fri
    5: COL_SAT,  # Sat
    6: COL_SUN,  # Sun
}

# Matches: "9-11am", "1:00-2:45pm", "11:00a-12:00p", "11:15-1:15pm"
TIME_RE = re.compile(
    r"(\d{1,2}(?::\d{2})?)\s*(a|am|p|pm)?\s*[-–]\s*(\d{1,2}(?::\d{2})?)\s*(a|am|p|pm)",
    re.IGNORECASE,
)


def _normalize_ampm(s: str | None) -> str | None:
    if not s:
        return None
    s = s.lower()
    if s in ("a", "am"):
        return "am"
    if s in ("p", "pm"):
        return "pm"
    return None


def parse_time(raw: str) -> tuple[str, str] | None:
    """Parse time range like '9-11am' or '11:00a-12:00p' into ('09:00', '11:00')."""
    m = TIME_RE.search(raw)
    if not m:
        return None
    start_s = m.group(1)
    start_period = _normalize_ampm(m.group(2))
    end_s = m.group(3)
    end_period = _normalize_ampm(m.group(4))

    def to_24h(t: str, ampm: str) -> str:
        if ":" in t:
            h, m = int(t.split(":")[0]), int(t.split(":")[1])
        else:
            h, m = int(t), 0
        if ampm == "pm" and h != 12:
            h += 12
        elif ampm == "am" and h == 12:
            h = 0
        return f"{h:02d}:{m:02d}"

    # Determine start period if not explicitly given
    if start_period is None:
        # Shared suffix: "9-11am" or "1:00-2:45pm" or "11:15-1:15pm"
        start_num = int(start_s.split(":")[0]) if ":" in start_s else int(start_s)
        end_num = int(end_s.split(":")[0]) if ":" in end_s else int(end_s)
        if end_period == "pm" and start_num > end_num and start_num >= 7:
            # e.g., "11:15-1:15pm" → start is AM, end is PM
            start_period = "am"
        else:
            start_period = end_period

    start_24 = to_24h(start_s, start_period)
    end_24 = to_24h(end_s, end_period)
    return start_24, end_24


def parse_header(page) -> tuple[str, str | None, str | None]:
    """Extract pool name and date range from page header text."""
    text = page.extract_text() or ""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    name = ""
    date_start = None
    date_end = None
    if lines:
        # First line: "Wrightwood Park | Summer 2026 | June 20 – August 2"
        header = lines[0]
        parts = [p.strip() for p in re.split(r"\s*\|\s*", header)]
        if parts:
            name = parts[0].replace(" Park", "").strip()
        # Look for date range in header
        date_match = re.search(
            r"((?:June|July|August|September)\s+\d{1,2})\s*[-–]\s*((?:June|July|August|September)\s+\d{1,2})",
            header,
            re.IGNORECASE,
        )
        if date_match:
            # Extract year from header
            year_match = re.search(r"20\d{2}", header)
            year = year_match.group(0) if year_match else "2026"
            date_start = _parse_date(date_match.group(1), year)
            date_end = _parse_date(date_match.group(2), year)
    return name, date_start, date_end


def _parse_date(date_str: str, year: str) -> str:
    """Convert 'June 20' + '2026' → '2026-06-20'."""
    months = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }
    parts = date_str.strip().split()
    if len(parts) >= 2:
        month = months.get(parts[0].lower(), "01")
        day = parts[1].strip(",")
        return f"{year}-{month}-{day.zfill(2)}"
    return f"{year}-01-01"


def _cell_text(val) -> str:
    """Normalize a cell value to a string."""
    if val is None:
        return ""
    return str(val).strip()


# Matches a single time like "11:00AM" or "9:00 AM" (with or without dash)
_PARTIAL_TIME_RE = re.compile(
    r"\d{1,2}(?::\d{2})?\s*(?:a|am|p|pm)", re.IGNORECASE
)


def _is_time(val: str) -> bool:
    """Check if a string looks like a time range."""
    return bool(TIME_RE.search(val))


def _has_time_fragment(val: str) -> bool:
    """Check if a string contains any time-like text (full range or partial)."""
    return bool(_PARTIAL_TIME_RE.search(val))


# Canonical swim type names (maps lowercase patterns to normalized names)
_TYPE_ALIASES = {
    "adult swim": "Adult Swim",
    "adult": "Adult Swim",
    "adults": "Adult Swim",
    "adultswim": "Adult Swim",
    "adult open swim": "Adult Swim",
    "adult/ lap swim": "Adult Lap Swim",
    "adult lap swim": "Adult Lap Swim",
    "adult lap": "Adult Lap Swim",
    "adult learn to swim": "Adult Learn to Swim",
    "senior swim": "Senior Swim",
    "senior": "Senior Swim",
    "seniors": "Senior Swim",
    "senior swim 60+": "Senior Swim",
    "senior open swim": "Senior Swim",
    "senior/adult": "Senior Swim",
    "open swim": "Open Swim",
    "open": "Open Swim",
    "parent & child swim": "Parent & Child Swim",
    "parent & child": "Parent & Child Swim",
    "parent and child swim": "Parent & Child Swim",
    "parent and child": "Parent & Child Swim",
    "parent + child swim": "Parent & Child Swim",
    "parent-child swim": "Parent & Child Swim",
    "parent/child swim": "Parent & Child Swim",
    "parentship swim": "Parent & Child Swim",
    "parent & tot swim": "Parent & Tot Swim",
    "parent and tot swim": "Parent & Tot Swim",
    "parent and tot": "Parent & Tot Swim",
    "parent/tot open swim": "Parent & Tot Swim",
    "tot swim": "Parent & Tot Swim",
    "day camp": "Day Camp",
    "day camp swim": "Day Camp",
    "daycamp": "Day Camp",
    "camp swim": "Day Camp",
    "camp": "Day Camp",
    "summer camp": "Day Camp",
    "teen swim": "Teen Swim",
    "teen": "Teen Swim",
    "teen open swim": "Teen Swim",
    "youth swim": "Youth Swim",
    "youth": "Youth Swim",
    "youth open swim": "Youth Open Swim",
    "youth/teen swim": "Youth/Teen Swim",
    "youth/teen open swim": "Youth/Teen Open Swim",
    "youth and teen swim": "Youth/Teen Swim",
    "youth/ teen swim": "Youth/Teen Swim",
    "youth /teen swim": "Youth/Teen Swim",
    "youth learn to swim": "Youth Learn to Swim",
    "youth learn swim": "Youth Learn to Swim",
    "learn to swim": "Learn to Swim",
    "learn to swim youth": "Youth Learn to Swim",
    "learn to swim tiny tot": "Learn to Swim",
    "youth/teen learn to swim": "Youth/Teen Learn to Swim",
    "youth/teen learn to swim*": "Youth/Teen Learn to Swim",
    "lap swim": "Lap Swim",
    "team sports": "Team Sports",
    "team sports**": "Team Sports",
    "family swim": "Family Swim",
}


def _normalize_swim_type(raw: str) -> str:
    """Clean up swim type text and map to canonical names."""
    # Replace newlines with spaces, collapse whitespace
    text = re.sub(r"\s+", " ", raw.replace("\n", " ")).strip()
    # Check if this is actually a time string that leaked into a type column
    if _PARTIAL_TIME_RE.match(text) or TIME_RE.search(text):
        return ""
    # Look up canonical name
    key = text.lower().strip()
    return _TYPE_ALIASES.get(key, text)


def _extract_blocks(table: list[list]) -> list[dict]:
    """Group table rows into time-slot blocks.

    Each block has:
      - wd_time: weekday time range string (or None)
      - we_time: weekend time range string (or None)
      - types: dict mapping column index → swim type string
    """
    # Skip header rows (first 2-3 rows that contain TIME/MON/TUE headers)
    data_rows = []
    header_done = False
    for row in table:
        if not header_done:
            c0 = _cell_text(_col(row, 0))
            c1 = _cell_text(_col(row, 1))
            if c0.upper() == "TIME" or c1.upper() == "MON":
                continue
            # Skip empty rows before data starts
            if all(_cell_text(c) == "" or c is None for c in row):
                continue
            header_done = True
        if header_done:
            data_rows.append(row)

    # Group consecutive non-empty rows into chunks (separated by empty rows).
    # Then split each chunk into sub-blocks at time-start boundaries.
    chunks = []
    current_chunk = []

    for row in data_rows:
        has_content = False
        c0 = _cell_text(_col(row, COL_TIME_WD))
        c6 = _cell_text(_col(row, COL_TIME_WE))
        if _has_time_fragment(c0) or _has_time_fragment(c6):
            has_content = True
        else:
            for i in [COL_MON, COL_TUE, COL_WED, COL_THU, COL_FRI, COL_SAT, COL_SUN]:
                val = _cell_text(_col(row, i))
                if val:
                    has_content = True
                    break

        if has_content:
            current_chunk.append(row)
        else:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = []

    if current_chunk:
        chunks.append(current_chunk)

    # Process each chunk, splitting on time-start boundaries when needed
    blocks = []
    for chunk in chunks:
        blocks.extend(_split_and_process(chunk))

    return blocks


def _split_and_process(rows: list[list]) -> list[dict]:
    """Split a chunk of rows into sub-blocks at time-start boundaries.

    Some PDFs have empty rows between blocks (easy), but others have
    contiguous rows with multiple time ranges. We detect new time-start
    fragments (e.g. "11:00AM -" or "11:00-12:00pm") in the weekday time
    column and split there if we've already accumulated time data.
    """
    # Detects start of a new time range in col 0
    time_start_re = re.compile(
        r"\d{1,2}(?::\d{2})?\s*(?:a|am|p|pm)?\s*[-–]", re.IGNORECASE
    )

    sub_blocks = []
    current = []
    has_time = False  # whether current sub-block has seen any time fragment

    for row in rows:
        c0 = _cell_text(_col(row, COL_TIME_WD))
        is_new_start = bool(time_start_re.search(c0))

        if is_new_start and has_time and current:
            # We already have time data and see a new time-start → split
            block = _process_block(current)
            if block:
                sub_blocks.append(block)
            current = [row]
            has_time = True
        else:
            current.append(row)
            if _has_time_fragment(c0):
                has_time = True

    if current:
        block = _process_block(current)
        if block:
            sub_blocks.append(block)

    return sub_blocks


def _col(row, idx):
    """Safely get a cell value from a row that might have fewer/more columns."""
    if idx < len(row):
        return row[idx]
    return None


def _process_block(rows: list[list]) -> dict | None:
    """Extract time and swim types from a group of rows."""
    types = {}

    # Collect time fragments (some PDFs split "11:00AM -" / "12:00PM" across rows)
    wd_time_parts = []
    we_time_parts = []
    mon_parts = []

    for row in rows:
        c0 = _cell_text(_col(row, COL_TIME_WD))
        c6 = _cell_text(_col(row, COL_TIME_WE))

        if c0:
            wd_time_parts.append(c0)
        if c6:
            we_time_parts.append(c6)

        # MON column: collect non-empty fragments
        mon_val = _cell_text(_col(row, COL_MON))
        if mon_val:
            mon_parts.append(mon_val)

        # TUE-FRI: take first non-None, non-empty value
        for col in [COL_TUE, COL_WED, COL_THU, COL_FRI]:
            if col not in types:
                val = _cell_text(_col(row, col))
                if val:
                    types[col] = _normalize_swim_type(val)

        # SAT, SUN: take first non-None, non-empty value
        for col in [COL_SAT, COL_SUN]:
            if col not in types:
                val = _cell_text(_col(row, col))
                if val:
                    types[col] = _normalize_swim_type(val)

    # Assemble MON swim type from fragments
    if mon_parts:
        types[COL_MON] = _normalize_swim_type(" ".join(mon_parts))

    # Reconstruct time ranges from fragments
    wd_time = " ".join(wd_time_parts) if wd_time_parts else None
    we_time = " ".join(we_time_parts) if we_time_parts else None

    if not wd_time and not we_time:
        return None

    return {"wd_time": wd_time, "we_time": we_time, "types": types}


def parse_pdf(pdf_path: str) -> dict:
    """Parse a pool schedule PDF into structured data.

    Returns:
        {
            "name": "Wrightwood",
            "date_start": "2026-06-20",
            "date_end": "2026-08-02",
            "slots": [
                {"day_of_week": 0, "start_time": "11:00", "end_time": "11:45",
                 "swim_type": "Parent & Tot Swim"},
                ...
            ]
        }
    """
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[0]
        name, date_start, date_end = parse_header(page)
        tables = page.extract_tables()
        if not tables:
            return {"name": name, "date_start": date_start, "date_end": date_end, "slots": []}

        table = tables[0]
        blocks = _extract_blocks(table)
        slots = []

        for block in blocks:
            wd_time = block["wd_time"]
            we_time = block["we_time"]
            types = block["types"]

            # Weekday slots (Mon-Fri)
            if wd_time:
                parsed = parse_time(wd_time)
                if parsed:
                    start, end = parsed
                    for day, col in [(0, COL_MON), (1, COL_TUE), (2, COL_WED),
                                     (3, COL_THU), (4, COL_FRI)]:
                        swim_type = types.get(col, "")
                        if swim_type:
                            slots.append({
                                "day_of_week": day,
                                "start_time": start,
                                "end_time": end,
                                "swim_type": swim_type,
                            })

            # Weekend slots (Sat-Sun)
            if we_time:
                parsed = parse_time(we_time)
                if parsed:
                    start, end = parsed
                    for day, col in [(5, COL_SAT), (6, COL_SUN)]:
                        swim_type = types.get(col, "")
                        if swim_type:
                            slots.append({
                                "day_of_week": day,
                                "start_time": start,
                                "end_time": end,
                                "swim_type": swim_type,
                            })

        return {
            "name": name,
            "date_start": date_start,
            "date_end": date_end,
            "slots": slots,
        }
