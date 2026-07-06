from config import HOTEL_SEARCH_RADIUS_KM, MAX_HOTEL_RESULTS
from tools import hotel_ranking
from tools.booking_links import verified_hotel_link
from tools.duffel import DuffelError, search_stays
from tools.flight import _airport_db, _coerce_bool, _coerce_choice  # shared helpers
from tools.geocoding import geocode_city
from tools.mock_hotels import mock_hotels

_HOTEL_SORTS = {"price", "rating", "review_score"}
_NULLISH = {"", "null", "none", "nil", "undefined"}


def _airport_coords(city):
    """Offline fallback: coordinates of an airport in the city (wider radius)."""
    key = (city or "").strip().lower()
    for _, details in _airport_db().items():
        name = details.get("city")
        if name and name.lower() == key and details.get("lat") is not None:
            return details["lat"], details["lon"], 30
    return None


def _city_coords(city):
    """Return (lat, lon, radius_km) for any city, or None if it can't be located.

    Resolves dynamically via the geocoder (no hardcoded city list); if the geocoder
    is unreachable, falls back to an airport's coordinates in that city.
    """
    coords = geocode_city(city)
    if coords:
        return coords[0], coords[1], HOTEL_SEARCH_RADIUS_KM
    return _airport_coords(city)


def _coerce_int(value, default=None, minimum=None):
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        n = value
    elif isinstance(value, str) and value.strip().lstrip("-").isdigit():
        n = int(value.strip())
    else:
        return default
    if minimum is not None and n < minimum:
        return minimum
    return n


def _coerce_float(value, default=None):
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def search_hotels(city, checkin, checkout, guests=1, rooms=1, room_type=None,
                  max_price=None, min_rating=None, breakfast_required=False,
                  free_cancellation_only=False, sort_by=None):
    guests = _coerce_int(guests, default=1, minimum=1) or 1
    rooms = _coerce_int(rooms, default=1, minimum=1) or 1
    if isinstance(room_type, str) and room_type.strip().lower() in _NULLISH:
        room_type = None

    preferences = {
        "max_price": _coerce_float(max_price, default=None),
        "min_rating": _coerce_float(min_rating, default=None),
        "breakfast_required": _coerce_bool(breakfast_required),
        "free_cancellation_only": _coerce_bool(free_cancellation_only),
        "sort_by": _coerce_choice(sort_by, _HOTEL_SORTS, None),
    }

    # Primary: live Duffel Stays availability (best-effort).
    live_error = None
    raw_results = []
    coords = _city_coords(city)
    if coords is None:
        live_error = f"Could not locate '{city}' for a live search."
    else:
        latitude, longitude, radius_km = coords
        try:
            raw_results = search_stays(
                checkin, checkout, latitude, longitude,
                guests=guests, rooms=rooms, radius_km=radius_km,
            )
        except DuffelError as e:
            live_error = str(e)

    if raw_results:
        result = hotel_ranking.recommend(raw_results, preferences, limit=MAX_HOTEL_RESULTS)
        result["source"] = "duffel_live"
    else:
        # Fail-safe: labelled mock hotels so we ALWAYS return a usable response.
        sample = mock_hotels(city, checkin, checkout, guests, rooms)
        result = hotel_ranking.rank_normalized(sample, preferences, limit=MAX_HOTEL_RESULTS)
        result["source"] = "mock"
        result["live_error"] = live_error
        result["note"] = (
            "Live hotel search was unavailable, so these are ILLUSTRATIVE SAMPLE "
            "hotels (not real availability). Prices/details are examples only — tell "
            "the user these are samples and to confirm on the booking site."
        )

    # Attach a verified, deterministic booking link to each recommended hotel.
    for hotel in result["hotels"]:
        hotel["booking_link"] = verified_hotel_link(
            hotel.get("name"), hotel.get("city") or city, checkin, checkout, guests,
        )

    result["requested_room_type"] = room_type
    result["stay"] = {"city": city, "checkin": checkin, "checkout": checkout,
                      "guests": guests, "rooms": rooms}
    return result


# JSON schema advertised to the model. Optional params are nullable because the
# model tends to fill every property (null for unused ones) and Groq validates
# the schema server-side; our code defaults/coerces them.
_NUM = {"type": ["integer", "string", "null"]}
_FLAG = {"type": ["boolean", "string", "null"]}  # weak models send "true"/"null" strings
SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_hotels",
        "description": "Search LIVE hotel availability (not cached) in a city for exact "
                       "dates. Returns hotels with price, star rating, guest score, "
                       "breakfast and free-cancellation info, and a verified booking "
                       "link. Filters/ranks by traveler preferences.",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Destination city, e.g. Rome."},
                "checkin": {"type": "string", "description": "Check-in date, YYYY-MM-DD."},
                "checkout": {"type": "string", "description": "Check-out date, YYYY-MM-DD."},
                "guests": {**_NUM, "description": "Number of adult guests. Defaults to 1."},
                "rooms": {**_NUM, "description": "Number of rooms required. Defaults to 1."},
                "room_type": {"type": ["string", "null"],
                              "description": "Room preference, e.g. 'twin/separate beds', "
                                             "'double', 'private room', 'apartment', 'dorm'."},
                "max_price": {"type": ["number", "string", "null"],
                              "description": "Max total price for the whole stay (offer currency)."},
                "min_rating": {**_NUM, "description": "Minimum star rating, e.g. 3."},
                "breakfast_required": {**_FLAG, "description": "Only hotels that include breakfast (true/false)."},
                "free_cancellation_only": {**_FLAG,
                                           "description": "Only hotels with free cancellation (true/false)."},
                "sort_by": {"type": ["string", "null"],
                            "description": "Ranking: 'price' (default), 'rating', or 'review_score'."},
            },
            "required": ["city", "checkin", "checkout"],
        },
    },
}
