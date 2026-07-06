
import os

from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.environ.get("LLM_API_KEY")
TRAVELPAYOUTS_TOKEN = os.environ.get("TRAVELPAYOUTS_TOKEN")

LLM_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "llama-3.3-70b-versatile"
TEMPERATURE = 0.7

MAX_TOOL_STEPS = 5

CURRENCY = "ils"


def require_llm_key():
    """Fail fast with a friendly message if the LLM key is missing."""
    if not LLM_API_KEY:
        raise SystemExit(
            "LLM_API_KEY is not set.\n"
            "Copy .env.example to .env and add your Groq API key "
            "(get one free at https://console.groq.com)."
        )
