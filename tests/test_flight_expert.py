"""Unit tests for the Flight Expert skill (pure functions, no I/O)."""
from skills import flight_expert


def _seg(origin, destination, checked=1, carry_on=1):
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


def _raw(offer_id="off_1", price="800.00", airline="BA", segments=None,
         refundable=False, currency="GBP"):
    return {
        "id": offer_id,
        "total_amount": price,
        "total_currency": currency,
        "owner": {"name": f"Airline {airline}", "iata_code": airline},
        "conditions": {
            "refund_before_departure": (
                {"allowed": True, "penalty_amount": "50.00", "penalty_currency": currency}
                if refundable else {"allowed": False}
            ),
            "change_before_departure": {"allowed": True, "penalty_amount": "30.00",
                                        "penalty_currency": currency},
        },
        "slices": [{"segments": segments or [_seg("TLV", "LHR")]}],
    }


# --- normalization -----------------------------------------------------------
def test_normalize_basic_fields():
    o = flight_expert.normalize_offer(_raw())
    assert o["price"] == 800.0
    assert o["currency"] == "GBP"
    assert o["airline_iata"] == "BA"
    assert o["stops"] == 0
    assert o["checked_bags"] == 1
    assert o["carry_on_bags"] == 1
    assert o["refundable"] is False
    assert o["changeable"] is True
    assert o["change_penalty"] == "30.00 GBP"


def test_normalize_counts_stops():
    raw = _raw(segments=[_seg("TLV", "IST"), _seg("IST", "ROM")])
    assert flight_expert.normalize_offer(raw)["stops"] == 1


def test_normalize_baggage_is_minimum_across_segments():
    # First leg has a checked bag, connecting leg does not -> not guaranteed.
    raw = _raw(segments=[_seg("TLV", "IST", checked=1), _seg("IST", "ROM", checked=0)])
    assert flight_expert.normalize_offer(raw)["checked_bags"] == 0


def test_normalize_refundable_penalty():
    o = flight_expert.normalize_offer(_raw(refundable=True))
    assert o["refundable"] is True
    assert o["refund_penalty"] == "50.00 GBP"


# --- preference filtering ----------------------------------------------------
def _norm(**kw):
    return flight_expert.normalize_offer(_raw(**kw))


def test_matches_max_stops():
    direct = _norm(segments=[_seg("TLV", "ROM")])
    one_stop = _norm(segments=[_seg("TLV", "IST"), _seg("IST", "ROM")])
    assert flight_expert.matches_preferences(direct, {"max_stops": 0})
    assert not flight_expert.matches_preferences(one_stop, {"max_stops": 0})


def test_matches_refundable_only():
    assert not flight_expert.matches_preferences(_norm(refundable=False), {"refundable_only": True})
    assert flight_expert.matches_preferences(_norm(refundable=True), {"refundable_only": True})


def test_matches_min_checked_bags():
    assert not flight_expert.matches_preferences(
        _norm(segments=[_seg("TLV", "ROM", checked=0)]), {"min_checked_bags": 1})
    assert flight_expert.matches_preferences(
        _norm(segments=[_seg("TLV", "ROM", checked=2)]), {"min_checked_bags": 1})


def test_matches_airline_include_exclude():
    ba = _norm(airline="BA")
    assert flight_expert.matches_preferences(ba, {"airlines_include": ["BA", "LY"]})
    assert not flight_expert.matches_preferences(ba, {"airlines_include": ["LY"]})
    assert not flight_expert.matches_preferences(ba, {"airlines_exclude": ["BA"]})


def test_matches_max_price():
    o = _norm(price="500.00")
    assert flight_expert.matches_preferences(o, {"max_price": 600})
    assert not flight_expert.matches_preferences(o, {"max_price": 400})


# --- expert notes ------------------------------------------------------------
def test_expert_notes_flag_nonrefundable_and_no_checked_bag():
    o = _norm(segments=[_seg("TLV", "ROM", checked=0, carry_on=1)], refundable=False)
    notes = " | ".join(flight_expert.expert_notes(o))
    assert "Direct" in notes
    assert "Carry-on only" in notes
    assert "Non-refundable" in notes


# --- recommend (end to end over the pure layer) ------------------------------
def test_recommend_sorts_and_limits_and_annotates():
    offers = [
        _raw("a", "900.00", "LY", segments=[_seg("TLV", "ROM")]),
        _raw("b", "400.00", "XX", segments=[_seg("TLV", "ROM")]),
        _raw("c", "650.00", "YY", segments=[_seg("TLV", "ROM")]),
    ]
    result = flight_expert.recommend(offers, {}, limit=2)
    assert result["total_found"] == 3
    assert [o["id"] for o in result["offers"]] == ["b", "c"]  # cheapest two, sorted
    assert all("expert_notes" in o for o in result["offers"])


def test_recommend_note_when_nothing_matches():
    offers = [_raw("a", "900.00", "XX", segments=[_seg("TLV", "ROM")], refundable=False)]
    result = flight_expert.recommend(offers, {"refundable_only": True})
    assert result["offers"] == []
    assert result["note"] is not None
