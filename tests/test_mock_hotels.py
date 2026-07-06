"""Tests for the mock hotel fail-safe generator."""
from tools import hotel_ranking
from tools.mock_hotels import mock_hotels


def test_mock_hotels_returns_normalized_shape():
    hotels = mock_hotels("Rome", "2026-11-07", "2026-11-09", guests=2, rooms=1)
    assert hotels
    h = hotels[0]
    # Same keys the ranking engine expects from a normalized hotel.
    for key in ("id", "name", "rating", "review_score", "price", "currency",
                "breakfast", "free_cancellation", "amenities"):
        assert key in h
    assert "Rome" in h["name"]
    assert h["currency"] == "ILS"


def test_mock_price_scales_with_nights():
    one = mock_hotels("Rome", "2026-11-07", "2026-11-08")[0]["price"]   # 1 night
    three = mock_hotels("Rome", "2026-11-07", "2026-11-10")[0]["price"]  # 3 nights
    assert three == one * 3


def test_mock_is_deterministic():
    a = mock_hotels("Paris", "2026-12-01", "2026-12-04")
    b = mock_hotels("Paris", "2026-12-01", "2026-12-04")
    assert [h["name"] for h in a] == [h["name"] for h in b]
    assert [h["price"] for h in a] == [h["price"] for h in b]


def test_mock_flows_through_ranking():
    hotels = mock_hotels("Rome", "2026-11-07", "2026-11-09")
    out = hotel_ranking.rank_normalized(hotels, {"breakfast_required": True}, limit=3)
    assert out["hotels"]
    assert all(h["breakfast"] for h in out["hotels"])
    assert all("expert_notes" in h for h in out["hotels"])


def test_mock_bad_dates_default_to_one_night():
    # Unparseable dates shouldn't crash; nights defaults to 1.
    hotels = mock_hotels("Rome", "not-a-date", None)
    assert hotels and hotels[0]["price"] > 0
