# Example prompts

Copy-paste these into the `You:` prompt after running `python main.py`.
They exercise the agent's main behaviors. (`exit` or `quit` to leave.)

## 1. The headline use case (flight + budget)
```
I want to fly to Rome with 2 friends for a weekend in November, budget 2500 ILS per person. I'm leaving from Tel Aviv.
```
Expect: a `search_flights` call (TLV→ROM), then a summary saying which options fit 2,500 ILS/person.

## 2. Missing info → one follow-up question
```
Find me flights to Italy next month.
```
Expect: the agent asks ONE specific question first (origin? which city? which dates?) instead of guessing.

## 3. Explicit route and single date
```
Cheapest flight from TLV to Barcelona on 2026-11-14?
```
Expect: a direct `search_flights` call. If a single day has no cached data, it should retry with the whole month.

## 4. Whole-month search (best for future dates)
```
What do flights from Tel Aviv to Athens cost across November 2026?
```
Expect: a `search_flights` call with date `2026-11`, returning several cached options.

## 5. Group total, not just per-person
```
Me and 3 friends (4 total) want to go from Tel Aviv to Paris in December. What's the total for everyone?
```
Expect: per-person AND total (per-person × 4) in the summary.

## 6. Hotel question → honest "not yet"
```
Can you also book us a hotel in Rome for those nights?
```
Expect: the agent honestly says it has no hotel tool yet (that's the next feature).

## 7. Availability honesty
```
Is that flight definitely bookable right now?
```
Expect: the agent explains prices are cached (recent searches), good for budgeting but not a live seat guarantee.

## 8. City names instead of IATA codes
```
Flights from Venice to Berlin in November 2026.
```
Expect: the tool converts "Venice"→VCE and "Berlin"→BER automatically.
