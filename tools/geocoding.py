import requests

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
_TIMEOUT_SECONDS = 10


def geocode_city(city):
    """Return (latitude, longitude) for a city name, or None if it can't resolve."""
    name = (city or "").strip()
    if not name:
        return None

    try:
        resp = requests.get(
            _GEOCODE_URL,
            params={"name": name, "count": 1, "language": "en", "format": "json"},
            timeout=_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        results = resp.json().get("results") or []
    except (requests.RequestException, ValueError):
        return None

    if not results:
        return None
    top = results[0]
    lat, lon = top.get("latitude"), top.get("longitude")
    if lat is None or lon is None:
        return None
    return lat, lon
