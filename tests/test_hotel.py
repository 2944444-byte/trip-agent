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


def _geocode_ok(monkeypatch, coords=(41.9028, 12.4964)):
    """Patch geocoding so tests never hit the network."""
    monkeypatch.setattr(hotel, "geocode_city", lambda *a, **k: coords)


def _patch(monkeypatch, results):
    _geocode_ok(monkeypatch)
    monkeypatch.setattr(hotel, "search_stays", lambda *a, **k: results)
    monkeypatch.setattr(hotel, "verified_hotel_link",
                        lambda *a, **k: {"url": "https://example.test/hotel",
                                         "verified": True, "status": 200})


def test_hotel_registered():
    assert AVAILABLE_TOOLS["search_hotels"] is search_hotels


def test_search_hotels_returns_ranked_with_links(monkeypatch):
    _patch(monkeypatch, [_result("a", 500, "Pricey"), _result("b", 200, "Cheap")])
    result = search_hotels("Rome", "2026-11-07", "2026-11-09", guests=3, room_type="twin")

    assert result["source"] == "duffel_live"
    assert [h["name"] for h in result["hotels"]] == ["Cheap", "Pricey"]  # cheapest first
    assert result["hotels"][0]["booking_link"]["verified"] is True
    assert result["stay"]["guests"] == 3
    assert result["requested_room_type"] == "twin"


def test_search_hotels_unlocatable_city_falls_back_to_mock(monkeypatch):
    # Geocoder can't resolve it and there's no airport match -> mock fail-safe.
    monkeypatch.setattr(hotel, "geocode_city", lambda *a, **k: None)
    monkeypatch.setattr(hotel, "_airport_coords", lambda *a, **k: None)
    monkeypatch.setattr(hotel, "verified_hotel_link",
                        lambda *a, **k: {"url": "x", "verified": False, "status": None})
    result = search_hotels("Zzznowhere", "2026-11-07", "2026-11-09")
    assert result["source"] == "mock"
    assert result["hotels"]  # always returns something
    assert "SAMPLE" in result["note"]


def test_search_hotels_duffel_error_falls_back_to_mock(monkeypatch):
    _geocode_ok(monkeypatch)

    def _boom(*a, **k):
        raise DuffelError("Duffel API error 403: stays not enabled")
    monkeypatch.setattr(hotel, "search_stays", _boom)
    monkeypatch.setattr(hotel, "verified_hotel_link",
                        lambda *a, **k: {"url": "x", "verified": True, "status": 200})
    result = search_hotels("Rome", "2026-11-07", "2026-11-09")

    assert result["source"] == "mock"
    assert "403" in result["live_error"]
    assert result["hotels"]
    assert all(h["booking_link"] for h in result["hotels"])


def test_search_hotels_mock_respects_max_price(monkeypatch):
    _geocode_ok(monkeypatch)
    monkeypatch.setattr(hotel, "search_stays",
                        lambda *a, **k: (_ for _ in ()).throw(DuffelError("403")))
    monkeypatch.setattr(hotel, "verified_hotel_link",
                        lambda *a, **k: {"url": "x", "verified": False, "status": None})
    # 1 night; cheapest mock is 180 ILS/night. Budget 200 keeps only the cheapest.
    result = search_hotels("Rome", "2026-11-07", "2026-11-08", max_price=200)
    assert result["source"] == "mock"
    assert all(h["price"] <= 200 for h in result["hotels"])
    assert result["hotels"]  # the 180 option survives


def test_search_hotels_guests_coerced_from_string(monkeypatch):
    _geocode_ok(monkeypatch)
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
