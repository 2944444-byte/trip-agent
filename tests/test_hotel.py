"""Tests for the hotel tool orchestration (Duffel Stays + links mocked)."""
import tools.hotel as hotel
from tools import AVAILABLE_TOOLS
from tools.duffel import DuffelError
from tools.hotel import SCHEMA, search_hotels


def _result(result_id, price, name):
    return {
        "id": result_id,
        "cheapest_rate_total_amount": str(price),
        "cheapest_rate_currency": "EUR",
        "accommodation": {
            "name": name, "rating": 4, "review_score": 8.0, "review_count": 500,
            "location": {"address": {"city_name": "Rome", "line_one": "Via Test 1"}},
            "amenities": [],
            "rooms": [{"rates": [{"total_amount": str(price), "total_currency": "EUR",
                                  "board_type": "breakfast",
                                  "cancellation_timeline": [{"refund_amount": str(price)}]}]}],
        },
    }


def _patch(monkeypatch, results):
    monkeypatch.setattr(hotel, "search_stays", lambda *a, **k: results)
    monkeypatch.setattr(hotel, "verified_hotel_link",
                        lambda *a, **k: {"url": "https://example.test/hotel",
                                         "verified": True, "status": 200})


def test_hotel_registered():
    assert AVAILABLE_TOOLS["search_hotels"] is search_hotels


def test_search_hotels_returns_ranked_with_links(monkeypatch):
    _patch(monkeypatch, [_result("a", 500, "Pricey"), _result("b", 200, "Cheap")])
    result = search_hotels("Rome", "2026-11-07", "2026-11-09", guests=3, room_type="twin")

    assert [h["name"] for h in result["hotels"]] == ["Cheap", "Pricey"]  # cheapest first
    assert result["hotels"][0]["booking_link"]["verified"] is True
    assert result["stay"]["guests"] == 3
    assert result["requested_room_type"] == "twin"


def test_search_hotels_unknown_city_returns_error(monkeypatch):
    # No network should happen; the city check fails first.
    result = search_hotels("Zzznowhere", "2026-11-07", "2026-11-09")
    assert "error" in result and "locate" in result["error"]


def test_search_hotels_duffel_error(monkeypatch):
    def _boom(*a, **k):
        raise DuffelError("Duffel API error 403: stays not enabled")
    monkeypatch.setattr(hotel, "search_stays", _boom)
    result = search_hotels("Rome", "2026-11-07", "2026-11-09")
    assert "error" in result and "403" in result["error"]


def test_search_hotels_guests_coerced_from_string(monkeypatch):
    captured = {}

    def _capture(checkin, checkout, lat, lon, guests=1, rooms=1, radius_km=10):
        captured["guests"] = guests
        return [_result("a", 200, "Cheap")]

    monkeypatch.setattr(hotel, "search_stays", _capture)
    monkeypatch.setattr(hotel, "verified_hotel_link",
                        lambda *a, **k: {"url": "x", "verified": False, "status": None})
    search_hotels("Rome", "2026-11-07", "2026-11-09", guests="4")
    assert captured["guests"] == 4


def test_hotel_schema_optional_params_are_nullable():
    props = SCHEMA["function"]["parameters"]["properties"]
    required = set(SCHEMA["function"]["parameters"]["required"])
    for name, spec in props.items():
        if name in required:
            continue
        assert "null" in spec["type"], f"optional param {name!r} must allow null"
