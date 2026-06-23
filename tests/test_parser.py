import os

from app.parser import parse_pdf, parse_time

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def test_parse_time_simple_am():
    assert parse_time("9-11am") == ("09:00", "11:00")


def test_parse_time_with_minutes():
    assert parse_time("1:00-2:45pm") == ("13:00", "14:45")


def test_parse_time_cross_period():
    assert parse_time("11:15-1:15pm") == ("11:15", "13:15")


def test_parse_time_simple_pm():
    assert parse_time("3:00-5:00pm") == ("15:00", "17:00")


def test_parse_time_evening():
    assert parse_time("5:15-7:00pm") == ("17:15", "19:00")


def test_parse_time_noon():
    assert parse_time("12:00-12:45pm") == ("12:00", "12:45")


def test_parse_time_morning():
    assert parse_time("11:00-11:45am") == ("11:00", "11:45")


def test_parse_time_noon_to_1pm():
    """12:00-1:00PM is noon to 1pm, not midnight to 1pm."""
    assert parse_time("12:00-1:00PM") == ("12:00", "13:00")


def test_parse_time_individual_markers():
    """Abbott-style: each time has its own am/pm marker."""
    assert parse_time("11:00a-12:00p") == ("11:00", "12:00")


def test_parse_time_individual_markers_same_period():
    assert parse_time("10:00a-11:00a") == ("10:00", "11:00")


def test_wrightwood_pdf():
    result = parse_pdf(os.path.join(FIXTURES, "wrightwood.pdf"))

    assert result["name"] == "Wrightwood"
    assert result["date_start"] == "2026-06-20"
    assert result["date_end"] == "2026-08-02"

    slots = result["slots"]
    assert len(slots) > 0

    # Check that we have slots for all 7 days
    days_present = {s["day_of_week"] for s in slots}
    assert days_present == {0, 1, 2, 3, 4, 5, 6}

    # Verify specific known slots from the PDF
    # Mon-Fri 11:00-11:45am: Parent & Tot Swim
    tot_swims = [s for s in slots if s["start_time"] == "11:00"
                 and s["end_time"] == "11:45" and s["day_of_week"] < 5]
    assert len(tot_swims) == 5
    for s in tot_swims:
        assert s["swim_type"] == "Parent & Tot Swim"

    # Mon-Fri 1:00-2:45pm: Day Camp
    day_camps = [s for s in slots if s["start_time"] == "13:00"
                 and s["end_time"] == "14:45" and s["day_of_week"] < 5]
    assert len(day_camps) == 5
    for s in day_camps:
        assert s["swim_type"] == "Day Camp"

    # Sat-Sun 9-11am: Parent & Tot Swim
    we_tot = [s for s in slots if s["start_time"] == "09:00"
              and s["end_time"] == "11:00" and s["day_of_week"] >= 5]
    assert len(we_tot) == 2
    for s in we_tot:
        assert s["swim_type"] == "Parent & Tot Swim"

    # Sat-Sun 3:45-4:45pm: Open Swim
    open_swims = [s for s in slots if s["start_time"] == "15:45"
                  and s["end_time"] == "16:45" and s["day_of_week"] >= 5]
    assert len(open_swims) == 2
    for s in open_swims:
        assert s["swim_type"] == "Open Swim"

    # Mon-Fri 5:15-7:00pm: Parent & Child Swim (no weekend equivalent)
    evening = [s for s in slots if s["start_time"] == "17:15" and s["day_of_week"] < 5]
    assert len(evening) == 5
    for s in evening:
        assert s["swim_type"] == "Parent & Child Swim"
    # No weekend slots at 5:15pm
    evening_we = [s for s in slots if s["start_time"] == "17:15" and s["day_of_week"] >= 5]
    assert len(evening_we) == 0
