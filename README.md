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
python main.py
```

See [PROMPTS.md](PROMPTS.md) for copy-paste example prompts to try once it's running.

## Testing

Unit tests cover the tool logic (passenger coercion, IATA conversion, registry
integrity, and `search_flights` response shaping). They hit no network and need no
API keys — the HTTP call is mocked.

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Environment variables

Set these via a local `.env` file (loaded automatically) — **never hardcode or
commit keys**.

| Variable               | Purpose                                                        |
| ---------------------- | -------------------------------------------------------------- |
| `LLM_API_KEY`          | Groq API key (base URL `https://api.groq.com/openai/v1`).      |
| `TRAVELPAYOUTS_TOKEN`  | Free token from travelpayouts.com (cached flight price data).  |

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
├── main.py            # entry point + the agent loop (run → decide → act → observe)
├── config.py          # constants + secrets (loads .env), key validation
├── requirements.txt
├── .env.example       # template; copy to .env and fill in
└── tools/
    ├── __init__.py    # tool registry: TOOLS (schemas) + AVAILABLE_TOOLS (dispatch)
    └── flight.py      # search_flights + its JSON schema
```

**Adding a tool:** write a plain function + a `SCHEMA` dict in a module under
`tools/`, then add one `(SCHEMA, function)` row to `_REGISTRY` in
`tools/__init__.py`. The dispatch name is derived from the schema, so it can't
drift from what the model is told.

## Roadmap and current status

1. **[DONE]** MVP: basic conversational agent, no tools.
2. **[DONE]** Tool 1 — flight search. Built first as a mock to teach the tool loop,
   then switched to the real Travelpayouts API. Same signature both times.
3. **[TODO]** Tool 2 — hotel search (same pattern as flights).
   Suggested signature: `search_hotels(city, checkin, checkout, guests=1, room_type=None)`.
4. **[TODO]** The **"Skill"** — promote the hotel tool into a dedicated hotel-expert
   module that categorizes hotels by type and applies logic such as: do **not**
   recommend a romantic couple's room when the group is friends. This is where the
   interesting reasoning lives.

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
