"""Tests for dynamic city geocoding (HTTP mocked)."""
import tools.geocoding as geocoding
from tools.geocoding import geocode_city


class _FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"status {self.status_code}")

    def json(self):
        return self._payload


def test_geocode_returns_coordinates(monkeypatch):
    payload = {"results": [{"name": "Rome", "latitude": 41.9028, "longitude": 12.4964}]}
    monkeypatch.setattr(geocoding.requests, "get", lambda *a, **k: _FakeResp(payload))
    assert geocode_city("Rome") == (41.9028, 12.4964)


def test_geocode_empty_result_returns_none(monkeypatch):
    monkeypatch.setattr(geocoding.requests, "get", lambda *a, **k: _FakeResp({"results": []}))
    assert geocode_city("Zzznowhere") is None


def test_geocode_blank_input_returns_none_without_call(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("should not call the API for blank input")
    monkeypatch.setattr(geocoding.requests, "get", _boom)
    assert geocode_city("") is None
    assert geocode_city(None) is None


def test_geocode_network_error_returns_none(monkeypatch):
    def _boom(*a, **k):
        raise geocoding.requests.RequestException("dns failure")
    monkeypatch.setattr(geocoding.requests, "get", _boom)
    assert geocode_city("Rome") is None


def test_geocode_missing_coords_returns_none(monkeypatch):
    payload = {"results": [{"name": "Nowhere"}]}  # no lat/lon
    monkeypatch.setattr(geocoding.requests, "get", lambda *a, **k: _FakeResp(payload))
    assert geocode_city("Nowhere") is None
