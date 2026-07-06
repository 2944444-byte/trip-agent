"""Hotel search tool (Duffel Stays-backed).

Orchestration layer with a stable signature. It:
  1. resolves a city name to search coordinates,
  2. asks Duffel Stays for live (request-time) availability,
  3. runs the hotel ranking engine to filter/rank/annotate by preferences,
  4. attaches a deterministic, HTTP-verified booking link to each hotel.

Results are request-time (live availability + pricing), not cached. Each carries
star rating, guest score, breakfast, and free-cancellation info. (With a Duffel
*test* token the data is realistically shaped but synthetic.)
"""
from config import HOTEL_SEARCH_RADIUS_KM, MAX_HOTEL_RESULTS
from tools import hotel_ranking
from tools.booking_links import verified_hotel_link
from tools.duffel import DuffelError, search_stays
from tools.flight import _airport_db  # reuse the cached IATA airport DB for fallback coords

# City -> (latitude, longitude) for the cities we support directly. Accurate
# city-centre coordinates so the radius search covers central accommodation.
_CITY_COORDS = {
    "tel aviv": (32.0853, 34.7818), "rome": (41.9028, 12.4964),
    "milan": (45.4642, 9.1900), "venice": (45.4408, 12.3155),
    "naples": (40.8518, 14.2681), "florence": (43.7696, 11.2558),
    "paris": (48.8566, 2.3522), "london": (51.5074, -0.1278),
    "barcelona": (41.3874, 2.1686), "athens": (37.9838, 23.7275),
    "berlin": (52.5200, 13.4050),
}


def _city_coords(city):
    """Return (lat, lon, radius_km) for a city, or None if we can't locate it.

    Curated city-centre coordinates are used when available; otherwise we fall
    back to the coordinates of an airport in that city (with a wider radius, since
    an airport can sit well outside the centre).
    """
    key = (city or "").strip().lower()
    if key in _CITY_COORDS:
        lat, lon = _CITY_COORDS[key]
        return lat, lon, HOTEL_SEARCH_RADIUS_KM

    for _, details in _airport_db().items():
        name = details.get("city")
        if name and name.lower() == key and details.get("lat") is not None:
            return details["lat"], details["lon"], 30
    return None


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
    """Search live hotel availability and apply Hotel Expert preferences.

    Args:
        city: destination city name (e.g. "Rome").
        checkin, checkout: stay dates, "YYYY-MM-DD".
        guests: number of adult guests (strings like "3" are coerced).
        rooms: number of rooms required.
        room_type: free-text room preference (e.g. "twin/separate beds",
            "double", "private room", "apartment"). Passed through for the Hotel
            Expert skill to reason about; Duffel search doesn't filter bed layout.
        max_price: drop hotels whose cheapest total is above this (stay total).
        min_rating: minimum star rating.
        breakfast_required: keep only hotels with a breakfast rate.
        free_cancellation_only: keep only hotels with a free-cancellation rate.
        sort_by: "price" (default), "rating", or "review_score".

    Returns:
        A dict with recommended hotels (each with a verified booking link) and the
        applied filters, or a dict with an "error" key.
    """
    guests = _coerce_int(guests, default=1, minimum=1) or 1
    rooms = _coerce_int(rooms, default=1, minimum=1) or 1

    coords = _city_coords(city)
    if coords is None:
        return {"error": f"Could not locate '{city}'. Try a major city name "
                         f"(e.g. Rome, Paris, Tel Aviv) or check the spelling."}
    latitude, longitude, radius_km = coords

    try:
        raw_results = search_stays(
            checkin, checkout, latitude, longitude,
            guests=guests, rooms=rooms, radius_km=radius_km,
        )
    except DuffelError as e:
        return {"error": str(e)}

    preferences = {
        "max_price": _coerce_float(max_price, default=None),
        "min_rating": _coerce_float(min_rating, default=None),
        "breakfast_required": breakfast_required,
        "free_cancellation_only": free_cancellation_only,
        "sort_by": sort_by,
    }
    result = hotel_ranking.recommend(raw_results, preferences, limit=MAX_HOTEL_RESULTS)

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
                "breakfast_required": {"type": ["boolean", "null"],
                                       "description": "Only hotels that include breakfast."},
                "free_cancellation_only": {"type": ["boolean", "null"],
                                           "description": "Only hotels with free cancellation."},
                "sort_by": {"type": ["string", "null"], "enum": ["price", "rating", "review_score", None],
                            "description": "Ranking: cheapest (default), rating, or review_score."},
            },
            "required": ["city", "checkin", "checkout"],
        },
    },
}
