
from urllib.parse import quote_plus

import requests

_VERIFY_TIMEOUT_SECONDS = 10
# Some sites 403 a bare client; present a normal browser UA for the check.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0 Safari/537.36"
)


def build_flight_search_url(origin, destination, depart_date, return_date=None, passengers=1):
    """Build a Google Flights search URL for a route/date (deterministic)."""
    q = f"Flights from {origin} to {destination} on {depart_date}"
    if return_date:
        q += f" returning {return_date}"
    if passengers and passengers > 1:
        q += f" for {passengers} passengers"
    return f"https://www.google.com/travel/flights?q={quote_plus(q)}"


def build_hotel_search_url(query, checkin, checkout, guests=1):
    """Build a Booking.com search URL for a search string/date (deterministic).

    `query` can be a city ("Rome") or a specific property + city ("Hotel Artemide,
    Rome") to land on that hotel's availability.
    """
    params = (
        f"ss={quote_plus(query)}"
        f"&checkin={checkin}&checkout={checkout}"
        f"&group_adults={max(int(guests), 1)}"
    )
    return f"https://www.booking.com/searchresults.html?{params}"


def verified_hotel_link(name, city, checkin, checkout, guests=1):
    """Build a Booking.com link for a specific hotel and verify it in one call."""
    query = f"{name}, {city}" if name and city else (name or city or "")
    url = build_hotel_search_url(query, checkin, checkout, guests)
    return verify_url(url)


def verify_url(url):
    """Make a real request and report whether the link is live.

    Returns {"url", "verified": bool, "status": int|None}. `verified` is True only
    when the server actually answered with a status below 400.
    """
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _BROWSER_UA},
            timeout=_VERIFY_TIMEOUT_SECONDS,
            allow_redirects=True,
            stream=True,  # don't download the whole body just to read the status
        )
        resp.close()
        return {"url": url, "verified": resp.status_code < 400, "status": resp.status_code}
    except requests.RequestException:
        return {"url": url, "verified": False, "status": None}


def verified_flight_link(origin, destination, depart_date, return_date=None, passengers=1):
    """Build a flight search link and verify it in one call."""
    url = build_flight_search_url(origin, destination, depart_date, return_date, passengers)
    return verify_url(url)
