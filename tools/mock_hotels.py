"""Mock hotel generator — the ultimate fail-safe fallback.

When every live source fails (no Stays scope, network down, etc.), we still return
something useful instead of crashing or looping. This produces ILLUSTRATIVE SAMPLE
hotels in the shape the ranking engine expects (see hotel_ranking.normalize_result
output), so they flow through the same filter/rank/annotate path.

These are NOT real availability. Results are tagged `source: "mock"` and the tool
attaches a clear note; the Hotel Expert skill discloses this to the user. Prices
are in ILS (to line up with ILS budgets) and vary so typical budget filters still
match something. Output is deterministic (no randomness) for reproducibility.
"""
from datetime import date

# (name suffix, star rating, guest score, price per night ILS, breakfast, free cancellation)
_ARCHETYPES = [
    ("City Hostel", 2, 8.1, 180, False, True),
    ("Central Inn", 3, 8.4, 260, True, True),
    ("Boutique Rooms", 4, 8.9, 380, True, False),
    ("Grand Hotel", 4, 8.6, 520, True, True),
    ("Riverside Apartments", 4, 9.0, 300, False, True),
    ("Old Town Suites", 5, 9.2, 700, True, False),
]

_AMENITIES = ["Free WiFi", "Air conditioning", "24-hour front desk"]


def _nights(checkin, checkout):
    try:
        d1 = date.fromisoformat(checkin)
        d2 = date.fromisoformat(checkout)
        return max((d2 - d1).days, 1)
    except (TypeError, ValueError):
        return 1


def mock_hotels(city, checkin, checkout, guests=1, rooms=1):
    """Return a deterministic list of normalized sample hotels for a city."""
    nights = _nights(checkin, checkout)
    city_label = (city or "the city").strip().title()

    hotels = []
    for i, (suffix, rating, score, per_night, breakfast, free_cancel) in enumerate(_ARCHETYPES):
        total = per_night * nights * max(rooms, 1)
        hotels.append({
            "id": f"mock_{i}",
            "name": f"{city_label} {suffix}",
            "rating": rating,
            "review_score": score,
            "review_count": 400 + i * 150,
            "price": float(total),
            "currency": "ILS",
            "city": city_label,
            "address": f"{10 + i} Central Street, {city_label}",
            "breakfast": breakfast,
            "free_cancellation": free_cancel,
            "amenities": list(_AMENITIES),
        })
    return hotels
