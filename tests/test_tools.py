"""Unit tests for the flight tool orchestration and shared helpers.

No network and no API keys: the Duffel call and the booking-link verification are
monkeypatched. Run with `python -m pytest`.
"""
import pytest

import tools.flight as flight
from tools import AVAILABLE_TOOLS, TOOLS
from tools.duffel import DuffelError
from tools.flight import SCHEMA, _coerce_passengers, _to_iata, get_iata_by_city, search_flights


# --- passenger coercion (the untrusted model/code boundary) ------------------
@pytest.mark.parametrize("value, expected", [
    (3, 3), ("3", 3), ("  2 ", 2), (1, 1),
    (0, 1), (-5, 1), ("0", 1), ("abc", 1), ("", 1), (None, 1),
    (2.5, 1), (True, 1),
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


# --- helpers to build fake Duffel offers -------------------------------------
def _segment(origin, destination, checked=1, carry_on=1):
    return {
        "origin": {"iata_code": origin},
        "destination": {"iata_code": destination},
        "departing_at": "2026-11-07T10:00:00",
        "arriving_at": "2026-11-07T14:00:00",
        "passengers": [{"baggages": [
            {"type": "checked", "quantity": checked},
            {"type": "carry_on", "quantity": carry_on},
        ]}],
    }


def _offer(offer_id, price, airline_iata, segments, refundable=False, currency="GBP"):
    return {
        "id": offer_id,
        "total_amount": str(price),
        "total_currency": currency,
        "owner": {"name": f"Airline {airline_iata}", "iata_code": airline_iata},
        "conditions": {
            "refund_before_departure": (
                {"allowed": True, "penalty_amount": "50.00", "penalty_currency": currency}
                if refundable else
                {"allowed": False, "penalty_amount": None, "penalty_currency": None}
            ),
            "change_before_departure": {"allowed": True, "penalty_amount": "30.00",
                                        "penalty_currency": currency},
        },
        "slices": [{"segments": segments}],
    }


@pytest.fixture
def patched_search(monkeypatch):
    """Patch Duffel + link verification; caller supplies the raw offers."""
    def _apply(raw_offers):
        monkeypatch.setattr(flight, "search_offers", lambda *a, **k: raw_offers)
        monkeypatch.setattr(
            flight, "verified_flight_link",
            lambda *a, **k: {"url": "https://example.test/flights", "verified": True, "status": 200},
        )
    return _apply


# --- search_flights orchestration -------------------------------------------
def test_search_flights_returns_recommendations_and_verified_link(patched_search):
    patched_search([
        _offer("off_1", 800, "BA", [_segment("TLV", "LHR")]),
        _offer("off_2", 650, "AZ", [_segment("TLV", "FCO")]),
    ])
    result = search_flights("Tel Aviv", "Rome", "2026-11-07")

    assert result["booking_link"]["verified"] is True
    assert result["route"]["origin"] == "TLV"
    assert result["total_found"] == 2
    # Cheapest first by default.
    assert [o["price"] for o in result["offers"]] == [650, 800]
    assert result["offers"][0]["expert_notes"]  # annotated


def test_search_flights_filters_by_max_stops(patched_search):
    direct = _offer("off_direct", 900, "LY", [_segment("TLV", "ROM")])
    one_stop = _offer("off_stop", 500, "XX",
                      [_segment("TLV", "IST"), _segment("IST", "ROM")])
    patched_search([direct, one_stop])

    result = search_flights("TLV", "ROM", "2026-11-07", max_stops=0)
    assert result["total_after_filters"] == 1
    assert result["offers"][0]["id"] == "off_direct"


def test_search_flights_refundable_only(patched_search):
    patched_search([
        _offer("off_nr", 400, "XX", [_segment("TLV", "ROM")], refundable=False),
        _offer("off_ref", 700, "YY", [_segment("TLV", "ROM")], refundable=True),
    ])
    result = search_flights("TLV", "ROM", "2026-11-07", refundable_only=True)
    assert [o["id"] for o in result["offers"]] == ["off_ref"]


def test_search_flights_passengers_coerced_from_string(monkeypatch):
    captured = {}

    def _capture(slices, passenger_count, **kwargs):
        captured["passengers"] = passenger_count
        return [_offer("off_1", 300, "XX", [_segment("TLV", "ROM")])]

    monkeypatch.setattr(flight, "search_offers", _capture)
    monkeypatch.setattr(flight, "verified_flight_link",
                        lambda *a, **k: {"url": "x", "verified": False, "status": None})

    search_flights("TLV", "ROM", "2026-11-07", passengers="3")
    assert captured["passengers"] == 3  # coerced from "3" (string) to 3 (int)


def test_search_flights_duffel_error_returns_error(monkeypatch):
    def _boom(*a, **k):
        raise DuffelError("Duffel API error 401: invalid token")

    monkeypatch.setattr(flight, "search_offers", _boom)
    result = search_flights("TLV", "ROM", "2026-11-07")
    assert "error" in result
    assert "401" in result["error"]


def test_schema_optional_params_are_nullable():
    """The model fills every property (null for unused ones); Groq validates the
    schema server-side, so every optional param MUST accept null."""
    props = SCHEMA["function"]["parameters"]["properties"]
    required = set(SCHEMA["function"]["parameters"]["required"])
    for name, spec in props.items():
        if name in required:
            continue
        assert "null" in spec["type"], f"optional param {name!r} must allow null"


def test_search_flights_accepts_null_optionals(monkeypatch):
    """Regression for the 400 where the model sent return_date/max_price = null and
    cabin_class = null. Our code must handle those gracefully."""
    captured = {}

    def _capture(slices, passenger_count, cabin_class=None, max_connections=None):
        captured["cabin_class"] = cabin_class
        return [_offer("off_1", 300, "XX", [_segment("TLV", "ATH")])]

    monkeypatch.setattr(flight, "search_offers", _capture)
    monkeypatch.setattr(flight, "verified_flight_link",
                        lambda *a, **k: {"url": "x", "verified": False, "status": None})

    # Mirrors the exact args the model produced in the failing generation.
    result = search_flights(
        "TLV", "ATH", "2026-11-14", return_date=None, passengers=1,
        cabin_class=None, max_stops=0, refundable_only=False, min_checked_bags=0,
        require_carry_on=False, airlines_include=[], airlines_exclude=[],
        max_price=None, sort_by="price",
    )
    assert "error" not in result
    assert captured["cabin_class"] == "economy"  # null defaulted safely
    assert result["offers"]
