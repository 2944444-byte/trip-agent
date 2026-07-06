"""The Duffel client must be search-only — it can never book / take a payment."""
import pytest

import tools.duffel as duffel
from tools.duffel import DuffelError


def test_only_search_endpoints_are_allowlisted():
    assert duffel._ALLOWED_ENDPOINTS == frozenset({
        duffel._OFFER_REQUESTS_URL, duffel._STAYS_SEARCH_URL,
    })
    # No orders/booking/payment endpoint may be present.
    assert not any("orders" in u or "payments" in u for u in duffel._ALLOWED_ENDPOINTS)


def test_post_refuses_non_search_endpoint(monkeypatch):
    # Even with a token set, POSTing to a booking endpoint is refused before any
    # network call — this code cannot buy anything.
    monkeypatch.setattr(duffel, "DUFFEL_API_TOKEN", "duffel_live_fake")

    def _should_not_run(*a, **k):
        raise AssertionError("network must not be reached for a blocked endpoint")

    monkeypatch.setattr(duffel.requests, "post", _should_not_run)
    with pytest.raises(DuffelError, match="non-search endpoint"):
        duffel._post(f"{duffel.DUFFEL_BASE_URL}/air/orders", {"anything": True})
