"""Unit tests for deterministic booking-link building and verification."""
import tools.booking_links as booking_links
from tools.booking_links import build_flight_search_url, build_hotel_search_url, verify_url


# --- deterministic URL building ----------------------------------------------
def test_build_flight_url_contains_route_and_domain():
    url = build_flight_search_url("TLV", "ROM", "2026-11-07")
    assert url.startswith("https://www.google.com/travel/flights?q=")
    assert "TLV" in url and "ROM" in url and "2026-11-07" in url


def test_build_flight_url_round_trip_and_passengers():
    url = build_flight_search_url("TLV", "ROM", "2026-11-07", return_date="2026-11-10", passengers=3)
    assert "returning" in url
    assert "2026-11-10" in url
    assert "3" in url


def test_build_hotel_url_contains_city_and_dates():
    url = build_hotel_search_url("Rome", "2026-11-07", "2026-11-10", guests=2)
    assert url.startswith("https://www.booking.com/searchresults.html?")
    assert "Rome" in url
    assert "checkin=2026-11-07" in url and "checkout=2026-11-10" in url
    assert "group_adults=2" in url


# --- verification (HTTP mocked) ----------------------------------------------
class _FakeResp:
    def __init__(self, status):
        self.status_code = status

    def close(self):
        pass


def test_verify_url_ok(monkeypatch):
    monkeypatch.setattr(booking_links.requests, "get", lambda *a, **k: _FakeResp(200))
    result = verify_url("https://example.test/x")
    assert result == {"url": "https://example.test/x", "verified": True, "status": 200}


def test_verify_url_client_error(monkeypatch):
    monkeypatch.setattr(booking_links.requests, "get", lambda *a, **k: _FakeResp(404))
    result = verify_url("https://example.test/missing")
    assert result["verified"] is False
    assert result["status"] == 404


def test_verify_url_network_failure(monkeypatch):
    def _boom(*a, **k):
        raise booking_links.requests.RequestException("dns failure")

    monkeypatch.setattr(booking_links.requests, "get", _boom)
    result = verify_url("https://example.test/down")
    assert result["verified"] is False
    assert result["status"] is None
