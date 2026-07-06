import os

from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.environ.get("LLM_API_KEY")
TRAVELPAYOUTS_TOKEN = os.environ.get("TRAVELPAYOUTS_TOKEN")
DUFFEL_API_TOKEN = os.environ.get("DUFFEL_API_TOKEN")

LLM_BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "meta-llama/llama-3.3-70b-instruct:free"
TEMPERATURE = 0.7

MAX_TOOL_STEPS = 5

CURRENCY = "ils"

DUFFEL_BASE_URL = "https://api.duffel.com"
DUFFEL_VERSION = "v2"

MAX_FLIGHT_RESULTS = 5
MAX_HOTEL_RESULTS = 5
HOTEL_SEARCH_RADIUS_KM = 8


def require_llm_key():
    if not LLM_API_KEY:
        raise SystemExit(
            "LLM_API_KEY is not set.\n"
            "Copy .env.example to .env and add your Groq API key "
            "(get one free at https://console.groq.com)."
        )
