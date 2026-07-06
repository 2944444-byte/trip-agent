"""Unit tests for the hotel ranking engine (pure functions, no I/O)."""
from tools import hotel_ranking


def _rate(total="300.00", board="room_only", refund=None, benefits=None):
    rate = {"total_amount": total, "total_currency": "EUR", "board_type": board,
            "benefits": benefits or []}
    if refund is not None:
        rate["cancellation_timeline"] = [{"refund_amount": refund, "before": "2026-11-01"}]
    return rate


def _result(result_id="res_1", price="300.00", name="Hotel Roma", rating=4,
            review=8.5, rates=None):
    return {
        "id": result_id,
        "cheapest_rate_total_amount": price,
        "cheapest_rate_currency": "EUR",
        "accommodation": {
            "name": name,
            "rating": rating,
            "review_score": review,
            "review_count": 1000,
            "location": {"address": {"city_name": "Rome", "line_one": "Via Test 1"}},
            "amenities": [{"type": "wifi", "description": "Free WiFi"}],
            "rooms": [{"rates": rates or [_rate()]}],
        },
    }


# --- normalization -----------------------------------------------------------
def test_normalize_basic_fields():
    h = hotel_ranking.normalize_result(_result())
    assert h["name"] == "Hotel Roma"
    assert h["rating"] == 4
    assert h["review_score"] == 8.5
    assert h["price"] == 300.0
    assert h["currency"] == "EUR"
    assert h["city"] == "Rome"
    assert "Free WiFi" in h["amenities"]


def test_breakfast_detected_from_board_type():
    h = hotel_ranking.normalize_result(_result(rates=[_rate(board="breakfast")]))
    assert h["breakfast"] is True


def test_breakfast_detected_from_benefits():
    rates = [_rate(board="room_only", benefits=[{"type": "breakfast_included"}])]
    assert hotel_ranking.normalize_result(_result(rates=rates))["breakfast"] is True


def test_no_breakfast_when_room_only():
    assert hotel_ranking.normalize_result(_result(rates=[_rate(board="room_only")]))["breakfast"] is False


def test_free_cancellation_when_full_refund():
    rates = [_rate(total="300.00", refund="300.00")]
    assert hotel_ranking.normalize_result(_result(rates=rates))["free_cancellation"] is True


def test_not_free_cancellation_when_partial_refund():
    rates = [_rate(total="300.00", refund="100.00")]
    assert hotel_ranking.normalize_result(_result(rates=rates))["free_cancellation"] is False


# --- filtering ---------------------------------------------------------------
def _norm(**kw):
    return hotel_ranking.normalize_result(_result(**kw))


def test_filter_max_price():
    h = _norm(price="500.00")
    assert hotel_ranking.matches_preferences(h, {"max_price": 600})
    assert not hotel_ranking.matches_preferences(h, {"max_price": 400})


def test_filter_min_rating():
    assert not hotel_ranking.matches_preferences(_norm(rating=2), {"min_rating": 3})
    assert hotel_ranking.matches_preferences(_norm(rating=4), {"min_rating": 3})


def test_filter_breakfast_required():
    no_bf = _norm(rates=[_rate(board="room_only")])
    yes_bf = _norm(rates=[_rate(board="breakfast")])
    assert not hotel_ranking.matches_preferences(no_bf, {"breakfast_required": True})
    assert hotel_ranking.matches_preferences(yes_bf, {"breakfast_required": True})


def test_filter_free_cancellation_only():
    refundable = _norm(rates=[_rate(total="300.00", refund="300.00")])
    non_ref = _norm(rates=[_rate(total="300.00", refund="0.00")])
    assert hotel_ranking.matches_preferences(refundable, {"free_cancellation_only": True})
    assert not hotel_ranking.matches_preferences(non_ref, {"free_cancellation_only": True})


# --- expert notes ------------------------------------------------------------
def test_expert_notes_flag_breakfast_and_cancellation():
    h = _norm(rating=4, rates=[_rate(board="room_only", refund="0.00")])
    notes = " | ".join(hotel_ranking.expert_notes(h))
    assert "4-star" in notes
    assert "No breakfast" in notes
    assert "Non-refundable" in notes


# --- recommend ---------------------------------------------------------------
def test_recommend_sorts_by_price_and_limits():
    results = [
        _result("a", "500.00", name="Pricey"),
        _result("b", "200.00", name="Cheap"),
        _result("c", "350.00", name="Mid"),
    ]
    out = hotel_ranking.recommend(results, {}, limit=2)
    assert out["total_found"] == 3
    assert [h["name"] for h in out["hotels"]] == ["Cheap", "Mid"]
    assert all("expert_notes" in h for h in out["hotels"])


def test_recommend_note_when_nothing_matches():
    results = [_result("a", "500.00", rating=2)]
    out = hotel_ranking.recommend(results, {"min_rating": 5})
    assert out["hotels"] == []
    assert out["note"] is not None
