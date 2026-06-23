"""ICS calendar file generation for swim slots."""

from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from icalendar import Calendar, Event


def make_ics(facility_name: str, swim_type: str, day_of_week: int,
             start_time: str, end_time: str,
             date_start: str, date_end: str, address: str = "") -> bytes:
    """Generate an .ics file for a recurring swim slot.

    Args:
        facility_name: e.g. "Wrightwood"
        swim_type: e.g. "Open Swim"
        day_of_week: 0=Mon ... 6=Sun
        start_time: "09:00" (24h)
        end_time: "11:00"
        date_start: "2026-06-20" (schedule start date)
        date_end: "2026-08-02" (schedule end date)
        address: facility street address

    Returns:
        ICS file content as bytes.
    """
    cal = Calendar()
    cal.add("prodid", "-//SwimChi//EN")
    cal.add("version", "2.0")

    sched_start = date.fromisoformat(date_start)
    sched_end = date.fromisoformat(date_end)

    # Find first occurrence of this day_of_week on or after schedule start
    # Python weekday: 0=Mon, matches our day_of_week
    days_ahead = day_of_week - sched_start.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first_date = sched_start + timedelta(days=days_ahead)

    sh, sm = map(int, start_time.split(":"))
    eh, em = map(int, end_time.split(":"))

    event = Event()
    event.add("summary", f"{swim_type} - {facility_name}")
    event.add("dtstart", datetime(first_date.year, first_date.month, first_date.day, sh, sm))
    event.add("dtend", datetime(first_date.year, first_date.month, first_date.day, eh, em))
    if address:
        event.add("location", address)

    # Weekly recurrence until schedule end
    ical_days = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
    event.add("rrule", {
        "freq": "weekly",
        "byday": ical_days[day_of_week],
        "until": datetime(sched_end.year, sched_end.month, sched_end.day, 23, 59, 59),
    })

    cal.add_component(event)
    return cal.to_ical()


def google_calendar_url(facility_name: str, swim_type: str, day_of_week: int,
                         start_time: str, end_time: str,
                         date_start: str, date_end: str, address: str = "") -> str:
    """Generate a Google Calendar event creation URL."""
    sched_start = date.fromisoformat(date_start)
    sched_end = date.fromisoformat(date_end)

    days_ahead = day_of_week - sched_start.weekday()
    if days_ahead < 0:
        days_ahead += 7
    first_date = sched_start + timedelta(days=days_ahead)

    sh, sm = map(int, start_time.split(":"))
    eh, em = map(int, end_time.split(":"))

    dt_start = datetime(first_date.year, first_date.month, first_date.day, sh, sm)
    dt_end = datetime(first_date.year, first_date.month, first_date.day, eh, em)

    ical_days = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
    # RRULE for Google: FREQ=WEEKLY;BYDAY=MO;UNTIL=20260802T235959Z
    until_str = sched_end.strftime("%Y%m%dT235959Z")
    recur = f"RRULE:FREQ=WEEKLY;BYDAY={ical_days[day_of_week]};UNTIL={until_str}"

    params = {
        "action": "TEMPLATE",
        "text": f"{swim_type} - {facility_name}",
        "dates": f"{dt_start.strftime('%Y%m%dT%H%M%S')}/{dt_end.strftime('%Y%m%dT%H%M%S')}",
        "location": address,
        "recur": recur,
    }
    return "https://www.google.com/calendar/render?" + urlencode(params)
