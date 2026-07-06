import pytest

import tools.flight as flight
from tools import AVAILABLE_TOOLS, TOOLS
from tools.flight import _coerce_passengers, _to_iata, get_iata_by_city, search_flights


# --- passenger coercion (the untrusted model/code boundary) ------------------
@pytest.mark.parametrize("value, expected", [
    (3, 3),            # already an int
    ("3", 3),          # model sent a string (the real 400-error case)
    ("  2 ", 2),       # surrounding whitespace
    (1, 1),
    (0, 1),            # non-positive -> default
    (-5, 1),
    ("0", 1),
    ("abc", 1),        # garbage -> default
    ("", 1),
    (None, 1),
    (2.5, 1),          # floats not accepted -> default
    (True, 1),         # bool is an int subclass but must not count as 1 passenger
])
def test_coerce_passengers(value, expected):
    assert _coerce_passengers(value) == expected


# --- IATA conversion ---------------------------------------------------------
def test_to_iata_passthrough_code():
    assert _to_iata("TLV") == "TLV"
    assert _to_iata("tlv") == "TLV"


def test_to_iata_curated_metro_map():
    assert _to_iata("Rome") == "ROM"
    assert _to_iata("tel aviv") == "TLV"


def test_to_iata_airportsdata_fallback():
    # Not in the curated map -> resolved via the airportsdata database.
    assert _to_iata("Sydney") is not None
    assert len(_to_iata("Sydney")) == 3


def test_to_iata_unknown_returns_input_upper():
    assert _to_iata("Zzzznowhere") == "ZZZZNOWHERE"


def test_get_iata_by_city_no_match_returns_none():
    assert get_iata_by_city("definitely not a city name 123") is None


# --- registry integrity (guards against the search_Cs name-drift bug) --------
def test_registry_names_match_dispatch_keys():
    schema_names = [t["function"]["name"] for t in TOOLS]
    assert schema_names == list(AVAILABLE_TOOLS.keys())


def test_search_flights_is_registered():
    assert AVAILABLE_TOOLS["search_flights"] is search_flights


# --- search_flights: no token -> friendly error ------------------------------
def test_search_flights_without_token(monkeypatch):
    monkeypatch.setattr(flight, "TRAVELPAYOUTS_TOKEN", None)
    result = search_flights("TLV", "ROM", "2026-11")
    assert "error" in result
    assert "TRAVELPAYOUTS_TOKEN" in result["error"]


# --- search_flights: response shaping (mocked HTTP) --------------------------
class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _fake_get_factory(payload):
    def _fake_get(url, params=None, headers=None, timeout=None):
        return _FakeResponse(payload)
    return _fake_get


def test_search_flights_shapes_options_and_totals(monkeypatch):
    monkeypatch.setattr(flight, "TRAVELPAYOUTS_TOKEN", "fake-token")
    payload = {
        "success": True,
        "data": {
            "ROM": {
                "0": {
                    "price": 800,
                    "airline": "AZ",
                    "flight_number": 123,
                    "departure_at": "2026-11-07T10:00:00",
                    "return_at": "2026-11-09T18:00:00",
                    "expires_at": "2026-07-10T00:00:00",
                }
            }
        },
    }
    monkeypatch.setattr(flight.requests, "get", _fake_get_factory(payload))

    result = search_flights("Tel Aviv", "Rome", "2026-11", passengers="3")

    assert isinstance(result, list) and len(result) == 1
    option = result[0]
    assert option["origin"] == "TLV"
    assert option["destination"] == "ROM"
    assert option["airline"] == "AZ"
    assert option["price_per_person_ils"] == 800
    assert option["total_price_ils"] == 2400  # 800 * 3 passengers (coerced from "3")


def test_search_flights_no_cached_data_returns_note(monkeypatch):
    monkeypatch.setattr(flight, "TRAVELPAYOUTS_TOKEN", "fake-token")
    payload = {"success": True, "data": {"ROM": {}}}
    monkeypatch.setattr(flight.requests, "get", _fake_get_factory(payload))

    result = search_flights("TLV", "ROM", "2026-11")
    assert "note" in result
    assert result["origin"] == "TLV"


def test_search_flights_api_failure_returns_error(monkeypatch):
    monkeypatch.setattr(flight, "TRAVELPAYOUTS_TOKEN", "fake-token")
    payload = {"success": False, "error": "bad request"}
    monkeypatch.setattr(flight.requests, "get", _fake_get_factory(payload))

    result = search_flights("TLV", "ROM", "2026-11")
    assert result["error"] == "bad request"


def test_search_flights_network_exception_returns_error(monkeypatch):
    monkeypatch.setattr(flight, "TRAVELPAYOUTS_TOKEN", "fake-token")

    def _boom(*args, **kwargs):
        raise flight.requests.RequestException("connection reset")

    monkeypatch.setattr(flight.requests, "get", _boom)
    result = search_flights("TLV", "ROM", "2026-11")
    assert "error" in result
    assert "flight API request failed" in result["error"]
