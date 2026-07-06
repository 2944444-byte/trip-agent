
import requests

from config import CURRENCY, TRAVELPAYOUTS_TOKEN

_API_URL = "https://api.travelpayouts.com/v1/prices/cheap"
_TIMEOUT_SECONDS = 15


class TravelpayoutsError(Exception):
    """Raised when Travelpayouts is unusable (no token, network, or API error)."""


def search_cheap_prices(origin, destination, date):
    if not TRAVELPAYOUTS_TOKEN:
        raise TravelpayoutsError("TRAVELPAYOUTS_TOKEN is not set.")

    params = {
        "origin": origin,
        "destination": destination,
        "depart_date": date,
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
        raise TravelpayoutsError(f"Travelpayouts request failed: {e}") from e

    if not payload.get("success", False):
        raise TravelpayoutsError(payload.get("error") or "Travelpayouts returned no data")

    # Response nests offers as data[destination][offer_key] = {...}.
    dest_block = next(iter(payload.get("data", {}).values()), {})
    offers = []
    for offer in dest_block.values():
        offers.append({
            "airline": offer.get("airline"),
            "flight_number": offer.get("flight_number"),
            "price": offer.get("price"),
            "departure_at": offer.get("departure_at"),
            "return_at": offer.get("return_at"),
            "expires_at": offer.get("expires_at"),
        })
    return offers
