_BREAKFAST_BOARDS = {"breakfast", "half_board", "full_board", "all_inclusive"}


def _to_float(amount):
    try:
        return float(amount)
    except (TypeError, ValueError):
        return None


def _rate_has_breakfast(rate):
    if rate.get("board_type") in _BREAKFAST_BOARDS:
        return True
    for benefit in rate.get("benefits") or []:
        if "breakfast" in (benefit.get("type") or "").lower():
            return True
    return False


def _rate_is_free_cancellation(rate, total):
    total = _to_float(total)
    for entry in rate.get("cancellation_timeline") or []:
        refund = _to_float(entry.get("refund_amount"))
        if refund is not None and total is not None and refund >= total - 0.01:
            return True
    return False


def _all_rates(accommodation):
    for room in accommodation.get("rooms") or []:
        for rate in room.get("rates") or []:
            yield rate


def normalize_result(raw):
    acc = raw.get("accommodation") or {}
    location = acc.get("location") or {}
    address = location.get("address") or {}
    price = _to_float(raw.get("cheapest_rate_total_amount"))

    breakfast = free_cancellation = False
    for rate in _all_rates(acc):
        if _rate_has_breakfast(rate):
            breakfast = True
        if _rate_is_free_cancellation(rate, rate.get("total_amount")):
            free_cancellation = True

    amenities = [a.get("description") or a.get("type")
                 for a in (acc.get("amenities") or [])]

    return {
        "id": raw.get("id"),
        "name": acc.get("name"),
        "rating": acc.get("rating"),
        "review_score": acc.get("review_score"),
        "review_count": acc.get("review_count"),
        "price": price,
        "currency": raw.get("cheapest_rate_currency"),
        "city": address.get("city_name") or address.get("city"),
        "address": address.get("line_one") or address.get("line1"),
        "breakfast": breakfast,
        "free_cancellation": free_cancellation,
        "amenities": [a for a in amenities if a][:8],
    }


def matches_preferences(hotel, prefs):
    max_price = prefs.get("max_price")
    if max_price is not None and hotel["price"] is not None and hotel["price"] > max_price:
        return False

    min_rating = prefs.get("min_rating")
    if min_rating is not None and (hotel["rating"] or 0) < min_rating:
        return False

    min_review = prefs.get("min_review_score")
    if min_review is not None and (hotel["review_score"] or 0) < min_review:
        return False

    if prefs.get("breakfast_required") and not hotel["breakfast"]:
        return False

    if prefs.get("free_cancellation_only") and not hotel["free_cancellation"]:
        return False

    return True


def _sort_key(sort_by):
    if sort_by == "rating":
        return lambda h: (-(h["rating"] or 0), h["price"] if h["price"] is not None else float("inf"))
    if sort_by == "review_score":
        return lambda h: (-(h["review_score"] or 0), h["price"] if h["price"] is not None else float("inf"))
    return lambda h: (h["price"] if h["price"] is not None else float("inf"), -(h["rating"] or 0))


def expert_notes(hotel):
    notes = []
    if hotel["rating"]:
        notes.append(f"{hotel['rating']}-star")
    if hotel["review_score"]:
        notes.append(f"Guest score {hotel['review_score']}")
    notes.append("Breakfast included" if hotel["breakfast"] else "No breakfast")
    notes.append("Free cancellation" if hotel["free_cancellation"]
                 else "Non-refundable / check cancellation terms")
    return notes


def recommend(raw_results, preferences=None, limit=5):
    normalized = [normalize_result(r) for r in raw_results]
    return rank_normalized(normalized, preferences, limit)


def rank_normalized(normalized, preferences=None, limit=5):
    prefs = preferences or {}
    matching = [h for h in normalized if matches_preferences(h, prefs)]
    matching.sort(key=_sort_key(prefs.get("sort_by")))

    top = matching[:limit]
    for hotel in top:
        hotel["expert_notes"] = expert_notes(hotel)

    note = None
    if normalized and not matching:
        note = ("Found accommodation, but none matched your preferences. Try raising "
                "the budget, lowering the rating requirement, or dropping "
                "breakfast/free-cancellation filters.")

    return {
        "hotels": top,
        "applied": {k: v for k, v in prefs.items() if v is not None},
        "total_found": len(normalized),
        "total_after_filters": len(matching),
        "note": note,
    }
