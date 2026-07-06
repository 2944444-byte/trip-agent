"""Flight search tool.

Plain Python behind a stable signature so the data source can be swapped without
touching the JSON schema or the agent loop. Currently backed by the Travelpayouts
(Aviasales) Data API, which returns *cached* prices from recent searches (refreshed
~every 48h), NOT live seat availability. Good for "which options fit the budget";
true availability verification needs a paid/approved provider (a later step).

Endpoint: GET https://api.travelpayouts.com/v1/prices/cheap
"""
import functools

import airportsdata
import requests

from config import CURRENCY, TRAVELPAYOUTS_TOKEN

_API_URL = "https://api.travelpayouts.com/v1/prices/cheap"
_TIMEOUT_SECONDS = 15

# Curated city -> IATA map. These are metropolitan codes (e.g. ROM covers all of
# Rome's airports) which are usually what a traveler means, so we check this
# before falling back to the airportsdata lookup below.
_CITY_TO_IATA = {
    "tel aviv": "TLV", "rome": "ROM", "milan": "MIL", "venice": "VCE",
    "naples": "NAP", "florence": "FLR", "paris": "PAR", "london": "LON",
    "barcelona": "BCN", "athens": "ATH", "berlin": "BER",
}


@functools.lru_cache(maxsize=1)
def _airport_db():
    """Load the IATA airport database once (it's a few MB) and cache it."""
    return airportsdata.load("IATA")


def get_iata_by_city(city_name):
    """Return the first IATA code whose airport city matches `city_name`.

    Returns None if nothing matches. Used as a fallback when a city isn't in the
    curated `_CITY_TO_IATA` map.
    """
    target = city_name.strip().lower()
    for iata, details in _airport_db().items():
        city = details.get("city")
        if city and city.lower() == target:
            return iata
    return None


def _to_iata(place):
    """Best-effort conversion of a city name (or code) into an IATA code.

    Order: already-a-code -> curated metro map -> airportsdata lookup -> as-is.
    """
    p = (place or "").strip()
    if len(p) == 3 and p.isalpha():
        return p.upper()

    if p.lower() in _CITY_TO_IATA:
        return _CITY_TO_IATA[p.lower()]

    return get_iata_by_city(p) or p.upper()


def _coerce_passengers(passengers):
    """Coerce the model-supplied passenger count into a positive int.

    The model/code boundary is untrusted: the model may send "3" (string) or a
    nonsense value. We validate here rather than trusting the schema.
    """
    if isinstance(passengers, bool):  # bool is an int subclass; reject it
        return 1
    if isinstance(passengers, int):
        return passengers if passengers > 0 else 1
    if isinstance(passengers, str) and passengers.strip().isdigit():
        n = int(passengers.strip())
        return n if n > 0 else 1
    return 1


def search_flights(origin, destination, date, passengers=1):
    """Search cached flight prices between two cities on a date.

    Args:
        origin: departure city name or IATA code (e.g. "Tel Aviv" or "TLV").
        destination: arrival city name or IATA code.
        date: "YYYY-MM-DD" for a day, or "YYYY-MM" for a whole month (a whole
            month is more likely to return cached data for future dates).
        passengers: traveler count; strings like "3" are coerced.

    Returns:
        A list of option dicts on success, or a dict with an "error"/"note" key.
    """
    passengers = _coerce_passengers(passengers)

    if not TRAVELPAYOUTS_TOKEN:
        return {"error": "TRAVELPAYOUTS_TOKEN is not set. Get a free token at travelpayouts.com."}

    origin_code = _to_iata(origin)
    destination_code = _to_iata(destination)
    params = {
        "origin": origin_code,
        "destination": destination_code,
        "depart_date": date,  # YYYY-MM-DD or YYYY-MM
        "currency": CURRENCY,
        "token": TRAVELPAYOUTS_TOKEN,
    }

    try:
        resp = requests.get(
            _API_URL,
            params=params,
            headers={"X-Access-Token": TRAVELPAYOUTS_TOKEN, "Accept-Encoding": "gzip, deflate"},
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as e:
        return {"error": f"flight API request failed: {e}"}

    if not payload.get("success", False):
        return {"error": payload.get("error") or "flight API returned no data"}

    # The API nests offers as data[destination][offer_key] = {...}.
    dest_block = next(iter(payload.get("data", {}).values()), {})
    options = []
    for offer in dest_block.values():
        price = offer.get("price")
        options.append({
            "origin": origin_code,
            "destination": destination_code,
            "airline": offer.get("airline"),
            "flight_number": offer.get("flight_number"),
            "departure_at": offer.get("departure_at"),
            "return_at": offer.get("return_at"),
            "price_per_person_ils": price,
            "total_price_ils": price * passengers if price else None,
            "price_expires_at": offer.get("expires_at"),
        })

    if not options:
        return {
            "note": "No cached prices for this exact route/date. Try a nearby date, "
                    "a whole month (YYYY-MM), or confirm the IATA codes.",
            "origin": origin_code,
            "destination": destination_code,
            "date": date,
        }
    return options


SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_flights",
        "description": "Search real (cached) flight prices between two cities on a "
                       "date. Returns options with airline, times, and ILS prices.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string",
                           "description": "Departure IATA city code, e.g. TLV for Tel Aviv."},
                "destination": {"type": "string",
                                "description": "Arrival IATA city code, e.g. ROM for Rome."},
                "date": {"type": "string",
                         "description": "Departure date YYYY-MM-DD, or a whole month YYYY-MM."},
                "passengers": {"type": ["integer", "string"],
                               "description": "Number of travelers, e.g. 3. Defaults to 1."},
            },
            "required": ["origin", "destination", "date"],
        },
    },
}
