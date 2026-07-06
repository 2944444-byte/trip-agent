import functools

import airportsdata

from config import CURRENCY, MAX_FLIGHT_RESULTS
from tools import flight_ranking
from tools.booking_links import verified_flight_link
from tools.duffel import DuffelError, search_offers
from tools.travelpayouts import TravelpayoutsError, search_cheap_prices

_CITY_TO_IATA = {
    "tel aviv": "TLV", "rome": "ROM", "milan": "MIL", "venice": "VCE",
    "naples": "NAP", "florence": "FLR", "paris": "PAR", "london": "LON",
    "barcelona": "BCN", "athens": "ATH", "berlin": "BER",
}


@functools.lru_cache(maxsize=1)
def _airport_db():    return airportsdata.load("IATA")


def get_iata_by_city(city_name):
    target = city_name.strip().lower()
    for iata, details in _airport_db().items():
        city = details.get("city")
        if city and city.lower() == target:
            return iata
    return None


def _to_iata(place):
    p = (place or "").strip()
    if len(p) == 3 and p.isalpha():
        return p.upper()
    if p.lower() in _CITY_TO_IATA:
        return _CITY_TO_IATA[p.lower()]
    return get_iata_by_city(p) or p.upper()


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


def _coerce_passengers(passengers):
    return _coerce_int(passengers, default=1, minimum=1) or 1


def search_flights(origin, destination, depart_date, return_date=None, passengers=1,
                   cabin_class="economy", max_stops=None, refundable_only=False,
                   min_checked_bags=None, require_carry_on=False,
                   airlines_include=None, airlines_exclude=None,
                   max_price=None, sort_by=None):
    passengers = _coerce_passengers(passengers)
    max_stops = _coerce_int(max_stops, default=None, minimum=0)
    cabin_class = cabin_class or "economy"  # model may send null

    origin_code = _to_iata(origin)
    destination_code = _to_iata(destination)

    slices = [{
        "origin": origin_code,
        "destination": destination_code,
        "departure_date": depart_date,
    }]
    if return_date:
        slices.append({
            "origin": destination_code,
            "destination": origin_code,
            "departure_date": return_date,
        })

    preferences = {
        "max_stops": max_stops,
        "refundable_only": refundable_only,
        "min_checked_bags": _coerce_int(min_checked_bags, default=None, minimum=0),
        "require_carry_on": require_carry_on,
        "airlines_include": airlines_include,
        "airlines_exclude": airlines_exclude,
        "max_price": _coerce_float(max_price, default=None),
        "sort_by": sort_by,
    }

    # Primary: live Duffel offers.
    duffel_error = None
    try:
        raw_offers = search_offers(
            slices, passengers, cabin_class=cabin_class, max_connections=max_stops,
        )
    except DuffelError as e:
        raw_offers, duffel_error = [], str(e)

    if raw_offers:
        result = flight_ranking.recommend(raw_offers, preferences, limit=MAX_FLIGHT_RESULTS)
        result["source"] = "duffel_live"
    else:
        result = _travelpayouts_fallback(
            origin_code, destination_code, depart_date, passengers, preferences,
            duffel_error,
        )
        if "error" in result:
            return result

    result["booking_link"] = verified_flight_link(
        origin_code, destination_code, depart_date, return_date, passengers,
    )
    result["route"] = {"origin": origin_code, "destination": destination_code,
                       "depart_date": depart_date, "return_date": return_date}
    return result


def _travelpayouts_fallback(origin, destination, depart_date, passengers, preferences,
                            duffel_error):
    try:
        cached = search_cheap_prices(origin, destination, depart_date)
        if not cached and len(depart_date) == 10:
            cached = search_cheap_prices(origin, destination, depart_date[:7])
    except TravelpayoutsError as tp_error:
        return {"error": "Flight search is unavailable right now.",
                "duffel_error": duffel_error,
                "travelpayouts_error": str(tp_error)}

    currency = CURRENCY.upper()
    offers = []
    for c in cached:
        price = c.get("price")
        offers.append({
            "airline": c.get("airline"),
            "airline_iata": c.get("airline"),
            "flight_number": c.get("flight_number"),
            "price": float(price) if price is not None else None,
            "currency": currency,
            "total_price": float(price) * passengers if price is not None else None,
            "departure_at": c.get("departure_at"),
            "return_at": c.get("return_at"),
            "stops": None, "checked_bags": None, "carry_on_bags": None,
            "refundable": None,
            "expert_notes": ["Cached price (Travelpayouts) — not live availability",
                             "Baggage & refund conditions not available from this source"],
        })

    max_price = preferences.get("max_price")
    if max_price is not None:
        offers = [o for o in offers if o["price"] is None or o["price"] <= max_price]
    offers.sort(key=lambda o: o["price"] if o["price"] is not None else float("inf"))
    offers = offers[:MAX_FLIGHT_RESULTS]

    ignored = [k for k in ("min_checked_bags", "require_carry_on", "refundable_only",
                           "max_stops", "airlines_include", "airlines_exclude")
               if preferences.get(k)]
    note = ("Live search (Duffel) was unavailable, so these are CACHED prices from "
            "Travelpayouts (not guaranteed bookable, prices ~48h old).")
    if ignored:
        note += f" These preferences couldn't be applied to cached data: {', '.join(ignored)}."

    return {
        "offers": offers,
        "source": "travelpayouts_cached",
        "applied": {"max_price": max_price} if max_price is not None else {},
        "total_found": len(cached),
        "total_after_filters": len(offers),
        "note": note,
        "duffel_error": duffel_error,
    }


_NUM = {"type": ["integer", "string", "null"]}
SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_flights",
        "description": "Search LIVE flight offers (not cached) between two cities and "
                       "filter/rank them by traveler preferences. Each offer includes "
                       "airline, price, stops, baggage allowance, and refund/change "
                       "conditions, plus a verified booking link for the route.",
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Departure city or IATA code, e.g. TLV."},
                "destination": {"type": "string", "description": "Arrival city or IATA code, e.g. ROM."},
                "depart_date": {"type": "string", "description": "Outbound date, YYYY-MM-DD."},
                "return_date": {"type": ["string", "null"],
                                "description": "Optional return date for a round trip, YYYY-MM-DD."},
                "passengers": {**_NUM, "description": "Number of adult travelers. Defaults to 1."},
                "cabin_class": {"type": ["string", "null"],
                                "enum": ["economy", "premium_economy", "business", "first", None],
                                "description": "Cabin class. Defaults to economy."},
                "max_stops": {**_NUM, "description": "Max connections per leg. 0 = direct only."},
                "refundable_only": {"type": ["boolean", "null"], "description": "Keep only refundable fares."},
                "min_checked_bags": {**_NUM, "description": "Require at least this many checked bags included."},
                "require_carry_on": {"type": ["boolean", "null"], "description": "Require a carry-on bag included."},
                "airlines_include": {"type": ["array", "null"], "items": {"type": "string"},
                                     "description": "Only these airline IATA codes, e.g. ['LY','AZ']."},
                "airlines_exclude": {"type": ["array", "null"], "items": {"type": "string"},
                                     "description": "Exclude these airline IATA codes."},
                "max_price": {"type": ["number", "string", "null"],
                              "description": "Drop offers above this amount (offer currency)."},
                "sort_by": {"type": ["string", "null"], "enum": ["price", "stops", None],
                            "description": "Ranking: cheapest first (default) or fewest stops."},
            },
            "required": ["origin", "destination", "depart_date"],
        },
    },
}
