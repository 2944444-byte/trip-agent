"""Low-level Duffel API client (Flights + Stays).

Thin wrapper around the two endpoints we need — creating a flight offer request
and searching for accommodation. Both return live (request-time, not cached)
results. Everything above this layer (normalization, expert filtering, booking
links) lives elsewhere so this file stays a pure I/O boundary.

Docs:
- Flights: https://duffel.com/docs/api/v2/offer-requests/create-offer-request
- Stays:   https://duffel.com/docs/api/v2/search
"""
import requests

from config import DUFFEL_API_TOKEN, DUFFEL_BASE_URL, DUFFEL_VERSION

_OFFER_REQUESTS_URL = f"{DUFFEL_BASE_URL}/air/offer_requests"
_STAYS_SEARCH_URL = f"{DUFFEL_BASE_URL}/stays/search"
_TIMEOUT_SECONDS = 30  # live searches are slower than a cache lookup


class DuffelError(Exception):
    """Raised when Duffel returns an error or is unreachable."""


def _headers():
    return {
        "Authorization": f"Bearer {DUFFEL_API_TOKEN}",
        "Duffel-Version": DUFFEL_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _post(url, data):
    """POST {"data": data} to Duffel and return the response's `data` object.

    Raises DuffelError on missing token, network failure, or a non-2xx response.
    """
    if not DUFFEL_API_TOKEN:
        raise DuffelError(
            "DUFFEL_API_TOKEN is not set. Get a free test token at "
            "https://app.duffel.com (Developers -> Access tokens)."
        )
    try:
        resp = requests.post(
            url, json={"data": data}, headers=_headers(), timeout=_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise DuffelError(f"Duffel request failed: {e}") from e

    if resp.status_code >= 400:
        # Surface Duffel's own error message when present; it's usually specific.
        raise DuffelError(f"Duffel API error {resp.status_code}: {_extract_error(resp)}")

    return resp.json().get("data", {})


def search_offers(slices, passenger_count, cabin_class="economy", max_connections=None):
    """Create an offer request and return the raw list of offer dicts.

    Args:
        slices: list of {"origin", "destination", "departure_date"} dicts. One
            slice = one-way; two slices = round-trip.
        passenger_count: number of adult travelers (>= 1).
        cabin_class: "economy" | "premium_economy" | "business" | "first".
        max_connections: cap on connections per slice (0 = non-stop only). None
            leaves it unconstrained.

    Returns:
        The list of raw offer dicts from Duffel (offers are returned inline by
        default).

    Raises:
        DuffelError: on missing token, network failure, or a non-2xx response.
    """
    data = {
        "slices": slices,
        "passengers": [{"type": "adult"} for _ in range(passenger_count)],
        "cabin_class": cabin_class,
    }
    if max_connections is not None:
        data["max_connections"] = max_connections

    return _post(_OFFER_REQUESTS_URL, data).get("offers", [])


def search_stays(check_in_date, check_out_date, latitude, longitude,
                 guests=1, rooms=1, radius_km=10):
    """Search live accommodation availability and return the raw results list.

    Args:
        check_in_date, check_out_date: ISO dates "YYYY-MM-DD".
        latitude, longitude: search center (the city's coordinates).
        guests: number of adult guests (>= 1).
        rooms: number of rooms required (>= 1).
        radius_km: search radius around the coordinates, in kilometres.

    Returns:
        The list of raw stay search-result dicts from Duffel.

    Raises:
        DuffelError: on missing token, network failure, or a non-2xx response.
    """
    data = {
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "rooms": rooms,
        "guests": [{"type": "adult"} for _ in range(guests)],
        "location": {
            "radius": radius_km,
            "geographic_coordinates": {"latitude": latitude, "longitude": longitude},
        },
    }
    return _post(_STAYS_SEARCH_URL, data).get("results", [])


def _extract_error(resp):
    """Pull a human-readable message out of a Duffel error response."""
    try:
        errors = resp.json().get("errors", [])
    except ValueError:
        return resp.text[:200]
    if errors:
        first = errors[0]
        return first.get("message") or first.get("title") or str(first)
    return resp.text[:200]
