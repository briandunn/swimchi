import os

from app.scraper import parse_list_view, parse_map_view, _get_last_page, _find_pool_pdf

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture():
    with open(os.path.join(FIXTURES, "scrap.html")) as f:
        return f.read()


def test_parse_list_view_count():
    html = _load_fixture()
    facilities = parse_list_view(html)
    # Page has some facilities (not all 82, just one page)
    assert len(facilities) > 0


def test_parse_list_view_first_facility():
    html = _load_fixture()
    facilities = parse_list_view(html)
    first = facilities[0]
    assert first["slug"] == "blackhawk-pool"
    assert first["name"] == "Blackhawk Pool"
    assert "2318 N. Lavergne" in first["address"]
    assert first["schedule_pdf_url"] is not None
    assert "Blackhawk" in first["schedule_pdf_url"]


def test_parse_list_view_skips_juneteenth():
    html = _load_fixture()
    facilities = parse_list_view(html)
    # California Pool has both Juneteenth and regular schedule PDFs
    california = [f for f in facilities if f["slug"] == "california-pool"]
    assert len(california) == 1
    assert "Juneteenth" not in california[0]["schedule_pdf_url"]
    assert "California" in california[0]["schedule_pdf_url"]


def test_parse_map_view():
    html = _load_fixture()
    coords = parse_map_view(html)
    assert len(coords) == 82
    # Check Abbott Pool coordinates
    abbott = coords.get("abbott-pool")
    assert abbott is not None
    assert abs(abbott["lat"] - 41.7209) < 0.01
    assert abs(abbott["lon"] - (-87.6222)) < 0.01


def test_get_last_page():
    html = _load_fixture()
    last_page = _get_last_page(html)
    assert last_page == 10


def test_find_pool_pdf_skips_citywide():
    links = [
        {"href": "juneteenth.pdf", "text": "Juneteenth 6/19/26 Citywide Pool Schedule"},
        {"href": "regular.pdf", "text": "June 20-Aug 2, 2026 Pool Schedule"},
    ]
    result = _find_pool_pdf(links)
    assert result["href"] == "regular.pdf"


def test_find_pool_pdf_single():
    links = [
        {"href": "schedule.pdf", "text": "June 20-Aug 2, 2026 Blackhawk Pool Schedule"},
    ]
    result = _find_pool_pdf(links)
    assert result["href"] == "schedule.pdf"
