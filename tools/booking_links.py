"""Deterministic, verified booking links.

Anti-hallucination strategy: the model NEVER writes a booking URL. Instead our
code builds the link from known-good templates (route + dates + guests) and then
makes a real HTTP request to confirm it resolves (status < 400). Only verified
links are handed back, so the agent can present "actual, active source links"
without any risk of an invented URL.

Duffel test offers are not bookable via a public one-click URL, so for flights we
return a metasearch link for the exact route/date (Google Flights). For hotels we
return a Booking.com search link for the city/dates (used once the hotel tool
lands).
"""
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


def build_hotel_search_url(city, checkin, checkout, guests=1):
    """Build a Booking.com search URL for a city/date (deterministic).

    Provided for the upcoming hotel tool; not yet wired into a live tool.
    """
    params = (
        f"ss={quote_plus(city)}"
        f"&checkin={checkin}&checkout={checkout}"
        f"&group_adults={max(int(guests), 1)}"
    )
    return f"https://www.booking.com/searchresults.html?{params}"


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
