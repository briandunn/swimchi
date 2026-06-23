"""Scrape Chicago Park District pool facility listings."""

import re

import httpx
from bs4 import BeautifulSoup

API_URL = (
    "https://www.chicagoparkdistrict.com/views/ajax"
    "?view_name=facilities&view_display_id=facility_by_type"
    "&view_args=2491&page={page}"
)

# PDFs with these words in the link text are citywide, not per-pool
SKIP_PATTERNS = re.compile(r"citywide|juneteenth", re.IGNORECASE)


def _parse_html(raw_html: str) -> BeautifulSoup:
    return BeautifulSoup(raw_html, "html.parser")


def _slug_from_href(href: str) -> str:
    """Extract slug from '/parks-facilities/blackhawk-pool'."""
    m = re.search(r"/parks-facilities/([^/\"?]+)", href)
    return m.group(1) if m else ""


def _find_pool_pdf(links: list[dict]) -> dict | None:
    """Find the per-pool schedule PDF, skipping citywide/Juneteenth PDFs."""
    for link in links:
        if SKIP_PATTERNS.search(link["text"]):
            continue
        if link["href"].endswith(".pdf") or ".pdf?" in link["href"]:
            return link
    return None


def parse_list_view(html: str) -> list[dict]:
    """Parse facility list view HTML into facility dicts.

    Returns list of:
        {"slug", "name", "address", "schedule_pdf_url", "schedule_pdf_text"}
    """
    doc = _parse_html(html)
    facilities = []
    for article in doc.select("article .facility"):
        title_el = article.select_one(".facility--title a")
        if not title_el:
            continue
        slug = _slug_from_href(title_el.get("href", ""))
        name = title_el.get_text(strip=True)

        address_el = article.select_one(".facility--address .address a")
        address = address_el.get_text(strip=True) if address_el else ""

        doc_links = []
        for a in article.select(".facility--documents a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True)
            doc_links.append({"href": href, "text": text})

        pdf = _find_pool_pdf(doc_links)
        facilities.append({
            "slug": slug,
            "name": name,
            "address": address,
            "schedule_pdf_url": pdf["href"] if pdf else None,
        })
    return facilities


def parse_map_view(html: str) -> dict[str, dict]:
    """Parse map view HTML for lat/lon coordinates.

    Returns dict of slug → {"lat": float, "lon": float}
    """
    doc = _parse_html(html)
    coords = {}
    for loc in doc.select(".geolocation-location"):
        lat = loc.get("data-lat")
        lng = loc.get("data-lng")
        link = loc.select_one("a[href*='/parks-facilities/']")
        if not link or not lat or not lng:
            continue
        slug = _slug_from_href(link.get("href", ""))
        if slug:
            coords[slug] = {"lat": float(lat), "lon": float(lng)}
    return coords


def _get_last_page(html: str) -> int:
    """Extract last page number from pager."""
    doc = _parse_html(html)
    last_link = doc.select_one(".pager__item--last a")
    if last_link:
        href = last_link.get("href", "")
        m = re.search(r"page=(\d+)", href)
        if m:
            return int(m.group(1))
    return 0


def fetch_page(page: int, client: httpx.Client) -> str:
    """Fetch a single page from the CPD API and return the HTML content."""
    url = API_URL.format(page=page)
    resp = client.get(url)
    resp.raise_for_status()
    data = resp.json()
    # The API returns an array; the HTML content is in element at index 3, key "data"
    return data[3]["data"]


def fetch_all(client: httpx.Client | None = None) -> list[dict]:
    """Fetch all facilities from CPD API.

    Returns list of:
        {"slug", "name", "address", "lat", "lon", "schedule_pdf_url"}
    """
    own_client = client is None
    if own_client:
        client = httpx.Client(timeout=30)

    try:
        # Fetch first page to get pagination info and map data
        html_page0 = fetch_page(0, client)
        last_page = _get_last_page(html_page0)

        # Parse map view from page 0 (contains all 82 facilities)
        coords = parse_map_view(html_page0)

        # Parse list view from all pages
        all_facilities = parse_list_view(html_page0)
        for page in range(1, last_page + 1):
            html = fetch_page(page, client)
            all_facilities.extend(parse_list_view(html))

        # Join coordinates
        for f in all_facilities:
            geo = coords.get(f["slug"], {})
            f["lat"] = geo.get("lat")
            f["lon"] = geo.get("lon")

        return all_facilities
    finally:
        if own_client:
            client.close()
