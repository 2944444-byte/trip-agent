# Travel Planning Agent

A travel planning agent built **from scratch** (no agent framework) to learn the
raw agent loop: **read → decide → act → observe**. It recommends flights (and,
soon, hotels), asks follow-up questions when info is missing, and calls real tools
to look up options.

Example target interaction:

> "I want to fly to Italy with 2 friends for a weekend in November, budget 2,500 ILS per person."

The agent recommends flights and hotels, asks follow-ups when info is missing, and
uses tools to look up real options.

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env      # then fill in your keys

python main.py            # command-line chat
# — or —
python web.py             # web chat UI at http://127.0.0.1:5000
```

See [PROMPTS.md](PROMPTS.md) for copy-paste example prompts to try once it's running.

## Web UI

`web.py` is a minimal [Flask](https://flask.palletsprojects.com/) wrapper around the
same agent loop (`run_agent_turn`). It serves a single self-contained chat page
(inline HTML/CSS/JS — no build step) and a `/chat` JSON endpoint; booking links in
replies are rendered clickable. Conversation state is kept in-process for one local
user (a demo UI, not a multi-user server) — the **Reset** button starts a fresh chat.

## Testing

Unit tests cover the tool logic (passenger coercion, IATA conversion, registry
integrity, the Flight Expert skill's filtering/ranking, booking-link building, and
the flight-tool orchestration). They hit no network and need no API keys — the
Duffel call and link verification are mocked.

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Environment variables

Set these via a local `.env` file (loaded automatically) — **never hardcode or
commit keys**.

| Variable               | Purpose                                                                   |
| ---------------------- | ------------------------------------------------------------------------- |
| `LLM_API_KEY`          | Groq API key (base URL `https://api.groq.com/openai/v1`).                 |
| `DUFFEL_API_TOKEN`     | Duffel Flights API token — live offers + baggage/refund conditions. Free test token at [app.duffel.com](https://app.duffel.com). |
| `TRAVELPAYOUTS_TOKEN`  | *(legacy, optional)* cached-price source, no longer used by the tool.     |

## Design decisions (do not silently reverse)

- **Build from scratch, no agent framework.** The goal is to learn the raw agent
  loop. Do **not** introduce LangChain/CrewAI/etc.
- **`openai` library pointed at Groq.** Groq is OpenAI-compatible, so we use the
  `openai` client and only change `base_url` + `model`. Nothing else.
- **Model:** `llama-3.3-70b-versatile` (good tool use, free tier). Fast
  alternative: `llama-3.1-8b-instant`.
- **Local tool calling.** The model *requests* a tool; **our** code executes it and
  feeds the result back. Tools are plain Python behind a stable signature so the
  data source can be swapped without touching the schema or the loop.
- **Secrets via environment variables only.** Never hardcode keys. Never commit them.

## Project layout

```
trip-agent/
├── main.py                     # entry point + the agent loop (run → decide → act → observe)
├── config.py                   # constants + secrets (loads .env), key validation
├── requirements.txt
├── .env.example                # template; copy to .env and fill in
├── skills/                     # SKILLS = expertise as Markdown, injected into the model
│   ├── loader.py               # reads SKILL.md files, injects them into the system prompt
│   ├── flight_expert/
│   │   └── SKILL.md            # Flight Expert skill: how to advise on flight offers
│   └── hotel_expert/
│       └── SKILL.md            # Hotel Expert skill: group dynamics, policy & amenity advice
└── tools/                      # TOOLS = code the model calls
    ├── __init__.py             # tool registry: TOOLS (schemas) + AVAILABLE_TOOLS (dispatch)
    ├── flight.py               # search_flights: IATA → Duffel → ranking → verified link
    ├── flight_ranking.py       # mechanical flight normalize/filter/rank/annotate engine
    ├── hotel.py                # search_hotels: city → Duffel Stays → ranking → verified links
    ├── hotel_ranking.py        # mechanical hotel normalize/filter/rank/annotate engine
    ├── duffel.py               # low-level Duffel API client — Flights + Stays (I/O boundary)
    └── booking_links.py        # deterministic + HTTP-verified booking links (anti-hallucination)
```

**Tools vs. skills.** A **tool** is code the model *calls* (a Python function +
JSON schema). A **skill** is expertise the model *reads* — a `SKILL.md` file with
frontmatter (`name`, `description`) plus instructions, loaded into the system
prompt by `skills/loader.py`. Tools do; skills advise.

**Adding a tool:** write a plain function + a `SCHEMA` dict in a module under
`tools/`, then add one `(SCHEMA, function)` row to `_REGISTRY` in
`tools/__init__.py`. The dispatch name is derived from the schema, so it can't
drift from what the model is told.

**Adding a skill:** create `skills/<name>/SKILL.md` with `name` + `description`
frontmatter and an instructions body. It's picked up automatically on startup.

**How the flight feature is layered:** `tools/flight.py` is thin orchestration —
it resolves IATA codes, calls `tools/duffel.py` for live offers, runs the
deterministic `tools/flight_ranking.py` engine (filter/rank/annotate by the
structured preferences), and attaches a verified link from `tools/booking_links.py`.
The **Flight Expert skill** (`skills/flight_expert/SKILL.md`) is the advisory
brain loaded into the model — it guides how to read baggage/fare conditions, weigh
trade-offs, keep groups together, and share only verified links. The model turns
the user's words into preference arguments; the ranking engine applies them; the
skill shapes the advice.

## Roadmap and current status

1. **[DONE]** MVP: basic conversational agent, no tools.
2. **[DONE]** Tool 1 — flight search. **Duffel** for live request-time offers, with an
   automatic **Travelpayouts cached-price fallback** (`tools/travelpayouts.py`) when
   Duffel is unavailable or returns nothing — so flight results always come back.
   The result's `source` field (`duffel_live` / `travelpayouts_cached`) drives the
   agent's honesty about data freshness. Same stable signature throughout.
3. **[DONE]** **Flight Expert skill** (`skills/flight_expert/SKILL.md`) — advises on
   baggage (checked vs. carry-on), refundable/change conditions, stops, cabin, airline
   preference, budget, and group-appropriate choices. The deterministic filter/rank
   is `tools/flight_ranking.py`; the Markdown skill guides how results are explained.
4. **[DONE]** **Verified booking links** — links are built deterministically by our
   code and HTTP-checked (status < 400) before being surfaced, so the agent can
   never hallucinate a URL. Only `verified: true` links are shared.
5. **[DONE]** Tool 2 — hotel search (`search_hotels`) backed by **Duffel Stays** for
   live availability, with a **mock fail-safe** (`tools/mock_hotels.py`): if the live
   search can't run (no Stays scope, unknown city, network error) or returns nothing,
   the tool returns clearly-labelled sample hotels (`source: "mock"`) so the agent
   always responds. Same layered pattern: `tools/hotel.py` orchestrates,
   `tools/hotel_ranking.py` filters/ranks, booking links are verified per hotel.
6. **[DONE]** **Hotel Expert skill** (`skills/hotel_expert/SKILL.md`) — advises like a
   seasoned consultant: group dynamics (friends → separate beds/apartment, not a
   romantic double unless it's a couple) and policy/amenity awareness (cancellation,
   breakfast, location/proximity to the centre, star rating vs. price). Discloses
   when results are `mock` samples vs `duffel_live`.
7. **[DONE]** **Reliability / no infinite loops** — the agent loop de-duplicates
   repeated identical tool calls within a turn and forces a text answer on the final
   step (`tool_choice="none"`), so a turn always returns a response. Duffel calls
   retry once on transient network errors but never on a 4xx.
8. **[DONE]** **Dynamic city resolution — no hardcoded city tables anywhere**
   (`tools/geocoding.py`). Hotels geocode the city to coordinates via the free,
   keyless Open-Meteo geocoder. Flights resolve city→IATA dynamically too: match
   `airportsdata` by city name, then use the geocoded coordinates to disambiguate
   same-named cities in different countries (e.g. London → LCY, not London, Ontario;
   Rome → FCO, not a US "Rome") and pick the nearest major airport. Both fall back
   to offline `airportsdata` lookups if the geocoder is unreachable.
9. **[TODO]** Optional: a live-mode Duffel token (real availability) and currency
   normalization.

> **Duffel Stays scope:** for *live* hotel results, enable **Stays** on your token at
> [app.duffel.com](https://app.duffel.com). Without it Duffel returns
> `403 ... This feature is not enabled`, and the tool automatically serves labelled
> **mock sample hotels** instead — so the agent still responds (just tell users the
> samples aren't real availability).

### Provider caveat (be honest with users)

With a Duffel **test** token, offers are realistically shaped but **synthetic** (not
real market prices/availability). A **live** token returns real airline offers;
some airlines require approval first. Prices come in each offer's own currency
(often not ILS), so the agent notes the currency rather than assuming a conversion.

## Key lessons learned (each cost a real debugging step)

- **The model/code boundary is untrusted.** The model returns JSON-ish tool
  arguments; validate and coerce types yourself. Concretely: Groq validates tool
  arguments against the JSON schema **server-side**, so a bad type fails with a
  `400` before your function runs. We hit exactly this: the model sent
  `"passengers": "3"` (string) against an `integer` schema → `400 tool_use_failed`.
  Fix = make the schema permissive (`"type": ["integer","string"]`) **and** coerce
  inside the function (see `_coerce_passengers`).
- **The message-role choreography for tool calls:** send messages with
  `tools=[...]` → model replies with `tool_calls` → append that assistant message →
  for each call, run the function and append a
  `{"role":"tool","tool_call_id":..., "content":...}` message → call the model again
  so it can use the results. The `tool_call_id` linkage is **mandatory**.
- **Real APIs speak IATA codes, not city names.** "Rome" must become `ROM`. We handle
  it two ways: tell the model to send codes in the schema description, and keep a
  small curated city→IATA map (plus an `airportsdata` fallback) for when it doesn't.
- **Flight API landscape in 2026 (verified July 2026):**
  - Amadeus Self-Service is being decommissioned **July 17, 2026** — do not build on it.
  - Kiwi/Skyscanner/Travelpayouts *search* APIs now require ~50,000 MAU + approval.
  - Travelpayouts (Aviasales) **Data API** is the genuinely free option: free
    affiliate signup, token auth, returns real prices by route/date/currency.
    Endpoint: `GET https://api.travelpayouts.com/v1/prices/cheap`.
- **Real-data caveat** (matters for the "verify availability" goal): the Travelpayouts
  Data API returns **cached** prices from recent searches (refreshed ~every 48h), NOT
  live seat availability. Great for "which options fit the budget," but it does not
  guarantee a seat is bookable right now. True availability verification requires a
  paid/approved provider — a later step. The system prompt already instructs the
  agent to be honest about this. Practical note: a specific future date may return no
  cached data; falling back to a whole month (`YYYY-MM`) usually returns results.

## Open questions to resolve

- Which free/affordable hotel data source to use (or start with a mock)?
- Should the "skill" be a true sub-agent (its own model call + prompt) or a
  deterministic ranking/filter layer over hotel results?
- Round-trip vs one-way handling, and how to pass return dates to the flight tool.
