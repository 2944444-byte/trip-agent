
import os

from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.environ.get("LLM_API_KEY")
TRAVELPAYOUTS_TOKEN = os.environ.get("TRAVELPAYOUTS_TOKEN")  # legacy cached-price source
DUFFEL_API_TOKEN = os.environ.get("DUFFEL_API_TOKEN")

LLM_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "llama-3.3-70b-versatile"
TEMPERATURE = 0.7

MAX_TOOL_STEPS = 5

CURRENCY = "ils"

# --- Duffel Flights API ------------------------------------------------------
# Request-time offers (not cached) including baggage + refund/change conditions.
# A test token (duffel_test_...) returns realistically shaped but synthetic data.
DUFFEL_BASE_URL = "https://api.duffel.com"
DUFFEL_VERSION = "v2"

# How many recommended offers the flight tool returns to the model at most.
MAX_FLIGHT_RESULTS = 5


def require_llm_key():
    """Fail fast with a friendly message if the LLM key is missing."""
    if not LLM_API_KEY:
        raise SystemExit(
            "LLM_API_KEY is not set.\n"
            "Copy .env.example to .env and add your Groq API key "
            "(get one free at https://console.groq.com)."
        )
