"""Tool registry.

Each tool module exports a callable plus a `SCHEMA` describing it to the model.
We register the (schema, function) pair once here and derive both the schema list
sent to the model and the name->function dispatch table from it. Deriving the
dispatch key from the schema's own name means the executed function can never
drift from the advertised tool name.

To add a tool (e.g. hotels): import its function + SCHEMA and add one row below.
"""
from tools.flight import SCHEMA as FLIGHT_SCHEMA, search_flights

_REGISTRY = [
    (FLIGHT_SCHEMA, search_flights),
    # (HOTEL_SCHEMA, search_hotels),  # TODO: add when the hotel tool lands.
]
# Note: the flight tool applies deterministic filtering/ranking via
# tools.flight_ranking and builds verified links via tools.booking_links. The
# advisory expertise is a Markdown skill (skills/flight_expert/SKILL.md) loaded
# into the model by skills.loader.

# Schemas advertised to the model, and the name -> implementation dispatch table.
TOOLS = [schema for schema, _ in _REGISTRY]
AVAILABLE_TOOLS = {schema["function"]["name"]: func for schema, func in _REGISTRY}
