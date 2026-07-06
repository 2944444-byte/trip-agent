"""The "Flight Expert" skill.

A deterministic reasoning layer over raw Duffel offers. It owns the flight
domain expertise: normalizing airline offers into a clean shape, filtering by
advanced traveler preferences (baggage, refundability, stops, airline), ranking
them, and annotating each with plain-language expert notes.

Design choice: this is a pure, side-effect-free layer (no network, no model
call) rather than a sub-agent. That keeps the expertise unit-testable and
deterministic; the language model's job is only to translate a user's words into
the structured `preferences` dict (via the tool schema), and our code applies the
judgment. Network concerns (fetching offers, verifying booking links) live in the
tools layer, not here.
"""

# --- Normalization -----------------------------------------------------------

def _to_float(amount):
    try:
        return float(amount)
    except (TypeError, ValueError):
        return None


def _baggage_counts(segment):
    """Count checked and carry-on bags for the first passenger on a segment."""
    passengers = segment.get("passengers") or []
    if not passengers:
        return 0, 0
    checked = carry_on = 0
    for bag in passengers[0].get("baggages") or []:
        qty = bag.get("quantity") or 0
        if bag.get("type") == "checked":
            checked += qty
        elif bag.get("type") == "carry_on":
            carry_on += qty
    return checked, carry_on


def _offer_baggage(slices):
    """Guaranteed baggage = the minimum included on any segment of the trip.

    You only reliably have a bag on every leg if every segment includes it, so we
    take the per-type minimum across all segments.
    """
    checked_per_segment, carry_on_per_segment = [], []
    for sl in slices:
        for seg in sl.get("segments") or []:
            checked, carry_on = _baggage_counts(seg)
            checked_per_segment.append(checked)
            carry_on_per_segment.append(carry_on)
    if not checked_per_segment:
        return 0, 0
    return min(checked_per_segment), min(carry_on_per_segment)


def _condition(conditions, key):
    """Return (allowed: bool, penalty: str|None) for a conditions sub-object."""
    block = (conditions or {}).get(key)
    if not block:
        return False, None
    allowed = bool(block.get("allowed"))
    penalty = None
    amount = block.get("penalty_amount")
    if allowed and amount is not None:
        currency = block.get("penalty_currency") or ""
        penalty = f"{amount} {currency}".strip()
    return allowed, penalty


def normalize_offer(raw):
    """Turn a raw Duffel offer into a clean, flat dict our layer understands."""
    slices = raw.get("slices") or []
    owner = raw.get("owner") or {}
    conditions = raw.get("conditions") or {}

    checked, carry_on = _offer_baggage(slices)
    refundable, refund_penalty = _condition(conditions, "refund_before_departure")
    changeable, change_penalty = _condition(conditions, "change_before_departure")

    trip_slices = []
    stops = 0
    for sl in slices:
        segments = sl.get("segments") or []
        stops = max(stops, max(len(segments) - 1, 0))
        first, last = (segments[0] if segments else {}), (segments[-1] if segments else {})
        trip_slices.append({
            "origin": (first.get("origin") or {}).get("iata_code"),
            "destination": (last.get("destination") or {}).get("iata_code"),
            "departing_at": first.get("departing_at"),
            "arriving_at": last.get("arriving_at"),
            "segments": len(segments),
        })

    return {
        "id": raw.get("id"),
        "price": _to_float(raw.get("total_amount")),
        "currency": raw.get("total_currency"),
        "airline": owner.get("name"),
        "airline_iata": owner.get("iata_code"),
        "stops": stops,
        "checked_bags": checked,
        "carry_on_bags": carry_on,
        "refundable": refundable,
        "refund_penalty": refund_penalty,
        "changeable": changeable,
        "change_penalty": change_penalty,
        "slices": trip_slices,
    }


# --- Preference filtering ----------------------------------------------------

def matches_preferences(offer, prefs):
    """Return True if a normalized offer satisfies every set preference."""
    if prefs.get("refundable_only") and not offer["refundable"]:
        return False

    max_stops = prefs.get("max_stops")
    if max_stops is not None and offer["stops"] > max_stops:
        return False

    min_checked = prefs.get("min_checked_bags")
    if min_checked is not None and offer["checked_bags"] < min_checked:
        return False

    if prefs.get("require_carry_on") and offer["carry_on_bags"] < 1:
        return False

    max_price = prefs.get("max_price")
    if max_price is not None and offer["price"] is not None and offer["price"] > max_price:
        return False

    include = prefs.get("airlines_include")
    if include and offer["airline_iata"] not in include:
        return False

    exclude = prefs.get("airlines_exclude")
    if exclude and offer["airline_iata"] in exclude:
        return False

    return True


# --- Ranking -----------------------------------------------------------------

def _sort_key(sort_by):
    if sort_by == "stops":
        return lambda o: (o["stops"], o["price"] if o["price"] is not None else float("inf"))
    # default: cheapest first, fewer stops as a tie-breaker
    return lambda o: (o["price"] if o["price"] is not None else float("inf"), o["stops"])


# --- Expert annotation -------------------------------------------------------

def expert_notes(offer):
    """Plain-language notes a knowledgeable travel agent would point out."""
    notes = []

    notes.append("Direct" if offer["stops"] == 0
                 else f"{offer['stops']} stop{'s' if offer['stops'] > 1 else ''}")

    if offer["checked_bags"] > 0:
        notes.append(f"Includes {offer['checked_bags']} checked bag(s)")
    elif offer["carry_on_bags"] > 0:
        notes.append("Carry-on only, no checked bag included")
    else:
        notes.append("No baggage included — verify before booking")

    if offer["refundable"]:
        notes.append(f"Refundable (penalty {offer['refund_penalty']})"
                     if offer["refund_penalty"] else "Refundable")
    else:
        notes.append("Non-refundable")

    return notes


# --- Public entry point ------------------------------------------------------

def recommend(raw_offers, preferences=None, limit=5):
    """Normalize -> filter -> rank -> annotate. Returns a structured result.

    Args:
        raw_offers: list of raw Duffel offer dicts.
        preferences: optional dict of traveler preferences (see the tool schema).
        limit: max number of offers to return.

    Returns:
        {"offers": [...annotated...], "applied": {...}, "total_found": int,
         "total_after_filters": int, "note": str|None}
    """
    prefs = preferences or {}
    normalized = [normalize_offer(o) for o in raw_offers]
    matching = [o for o in normalized if matches_preferences(o, prefs)]
    matching.sort(key=_sort_key(prefs.get("sort_by")))

    top = matching[:limit]
    for offer in top:
        offer["expert_notes"] = expert_notes(offer)

    note = None
    if normalized and not matching:
        note = ("Found offers, but none matched your preferences. Try relaxing "
                "them (e.g. allow stops, drop refundable-only, or raise the budget).")

    return {
        "offers": top,
        "applied": {k: v for k, v in prefs.items() if v is not None},
        "total_found": len(normalized),
        "total_after_filters": len(matching),
        "note": note,
    }
