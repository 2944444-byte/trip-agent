"""Low-level Duffel Flights API client.

Thin wrapper around the one endpoint we need: creating an offer request, which
returns live (request-time, not cached) offers from airlines. Everything above
this layer (normalization, expert filtering, booking links) lives elsewhere so
this file stays a pure I/O boundary.

Docs: https://duffel.com/docs/api/v2/offer-requests/create-offer-request
"""
import requests

from config import DUFFEL_API_TOKEN, DUFFEL_BASE_URL, DUFFEL_VERSION

_OFFER_REQUESTS_URL = f"{DUFFEL_BASE_URL}/air/offer_requests"
_TIMEOUT_SECONDS = 30  # airline searches are slower than a cache lookup


class DuffelError(Exception):
    """Raised when Duffel returns an error or is unreachable."""


def _headers():
    return {
        "Authorization": f"Bearer {DUFFEL_API_TOKEN}",
        "Duffel-Version": DUFFEL_VERSION,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


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
    if not DUFFEL_API_TOKEN:
        raise DuffelError(
            "DUFFEL_API_TOKEN is not set. Get a free test token at "
            "https://app.duffel.com (Developers -> Access tokens)."
        )

    data = {
        "slices": slices,
        "passengers": [{"type": "adult"} for _ in range(passenger_count)],
        "cabin_class": cabin_class,
    }
    if max_connections is not None:
        data["max_connections"] = max_connections

    try:
        resp = requests.post(
            _OFFER_REQUESTS_URL,
            json={"data": data},
            headers=_headers(),
            timeout=_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise DuffelError(f"Duffel request failed: {e}") from e

    if resp.status_code >= 400:
        # Surface Duffel's own error message when present; it's usually specific.
        detail = _extract_error(resp)
        raise DuffelError(f"Duffel API error {resp.status_code}: {detail}")

    payload = resp.json()
    return payload.get("data", {}).get("offers", [])


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
