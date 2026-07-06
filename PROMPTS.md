# Example prompts

Copy-paste these into the `You:` prompt after running `python main.py`.
They exercise the agent's main behaviors. (`exit` or `quit` to leave.)

> Needs `DUFFEL_API_TOKEN` set in `.env` (free test token at app.duffel.com).
> With a *test* token the offers are realistically shaped but synthetic.

## 1. The headline use case (flight + budget + preferences)
```
I want to fly to Rome with 2 friends for a weekend in November, leaving Tel Aviv on 2026-11-07 and back on 2026-11-09. Budget around 2500 per person, and I'd like a checked bag included.
```
Expect: a round-trip `search_flights` call with `passengers=3`, `min_checked_bags=1`, then a summary noting baggage, price, currency, and which fit budget — plus the verified booking link.

## 2. Missing info → one follow-up question
```
Find me flights to Italy next month.
```
Expect: ONE specific question first (origin? which city? which date?) instead of guessing.

## 3. Direct flights only
```
Only direct flights from TLV to Athens on 2026-11-14, cheapest first.
```
Expect: `max_stops=0`, `sort_by=price`. Each result annotated "Direct".

## 4. Refundable / flexible fares
```
I need a refundable ticket from Tel Aviv to Paris on 2026-12-01, business class.
```
Expect: `refundable_only=true`, `cabin_class=business`. Non-refundable offers filtered out; refund penalties surfaced.

## 5. Baggage-conscious
```
Cheapest TLV to Barcelona on 2026-11-20 that includes a checked bag and a carry-on.
```
Expect: `min_checked_bags=1`, `require_carry_on=true`. Offers without a checked bag are dropped.

## 6. Airline preference
```
Flights from Tel Aviv to London on 2026-11-10, but not on low-cost carriers — prefer El Al (LY) or British Airways (BA).
```
Expect: `airlines_include=["LY","BA"]`.

## 7. Booking link must be real (anti-hallucination check)
```
Give me the booking link for that flight.
```
Expect: the agent shares ONLY the verified `booking_link.url` from the tool result. If it wasn't verified, it says a verified link isn't available — it must NOT invent a URL.

## 8. Hotel question → honest "not yet"
```
Can you also book us a hotel in Rome for those nights?
```
Expect: the agent honestly says it has no hotel tool yet (the next feature).
