# Example prompts

Copy-paste these into the `You:` prompt after running `python main.py`.
(`exit` or `quit` to leave.)

> **Data sources.** Flights try Duffel (live) first and fall back to Travelpayouts
> (cached ILS prices) if Duffel is unavailable — so flight results always come back.
> Hotels use Duffel Stays, which needs the **Stays** scope on your token; without it
> you'll get a graceful "feature not enabled" message.

---

## Full-trip planning (flights + hotels together)

### 1. The headline trip
```
I want to fly to Rome with 2 friends for a weekend, leaving Tel Aviv on 2026-11-07 and back on 2026-11-09. Budget about 2500 ILS per person for flights, and a hotel around 600 total with breakfast. We want a checked bag on the flight.
```
Expect: a `search_flights` call (round trip, `passengers=3`, `min_checked_bags=1`, `max_price=2500`) **and** a `search_hotels` call (`guests=3`, `breakfast_required=true`, `max_price=600`). The agent should keep the 3 friends together, recommend **separate beds** (not one double), and give verified booking links for both.

### 2. Couple's city break
```
Plan a trip to Paris for me and my partner, 2026-12-01 to 2026-12-04. Direct flights from Tel Aviv, and a central 4-star romantic hotel.
```
Expect: flights with `max_stops=0`; hotel with `min_rating=4` — a double room is appropriate here (contrast with the friends trip).

---

## Flights

### 3. Missing info → one follow-up
```
Find me flights to Italy next month.
```
Expect: ONE specific question first (origin? which city? which date?).

### 4. Direct only, cheapest first
```
Only direct flights from TLV to Athens on 2026-11-14, cheapest first.
```
Expect: `max_stops=0`, `sort_by=price`.

### 5. Refundable / flexible business fare
```
I need a refundable ticket from Tel Aviv to Paris on 2026-12-01, business class.
```
Expect: `refundable_only=true`, `cabin_class=business`. (If the result `source` is cached, the agent should say refundability couldn't be confirmed.)

### 6. Baggage-conscious
```
Cheapest TLV to Barcelona on 2026-11-20 that includes a checked bag and a carry-on.
```
Expect: `min_checked_bags=1`, `require_carry_on=true`.

---

## Hotels

### 7. Group of friends (group dynamics)
```
Find a hotel in Rome for 3 friends, 2026-11-07 to 2026-11-09, budget around 600 total, breakfast included and free cancellation.
```
Expect: `guests=3`, `breakfast_required=true`, `free_cancellation_only=true`, `max_price=600`. The Hotel Expert recommends **separate beds / multiple rooms or an apartment**, and calls out cancellation, breakfast, rating, and location.

### 8. Family with a budget
```
A family-friendly hotel in Barcelona, 2 adults, 2026-12-20 to 2026-12-27, at least 3 stars, free cancellation.
```
Expect: `min_rating=3`, `free_cancellation_only=true`; an apartment/family room is a reasonable suggestion.

---

## Honesty & anti-hallucination

### 9. Booking link must be real
```
Give me the booking link for the first option.
```
Expect: only the verified `booking_link.url` from the tool result — never an invented URL.

### 10. Is it live?
```
Is that flight price live and definitely bookable?
```
Expect: the agent checks the `source` — honest that cached (Travelpayouts) prices are ~48h old and not a guaranteed seat, while live (Duffel) offers are request-time; either way it's confirmed only at booking.
