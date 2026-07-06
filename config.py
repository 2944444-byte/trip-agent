"""Central configuration for the travel agent.

All tunables (model, temperature, endpoints, secrets) live here so the rest of
the code never hardcodes them. Secrets come from the environment only; a local
`.env` file is loaded automatically for convenience (never commit it).
"""
import os

from dotenv import load_dotenv

# Load a local .env into the process environment if present. Real environment
# variables always win over .env values, which is what we want in production.
load_dotenv()

# --- Secrets (environment only, never hardcode) ------------------------------
LLM_API_KEY = os.environ.get("LLM_API_KEY")
TRAVELPAYOUTS_TOKEN = os.environ.get("TRAVELPAYOUTS_TOKEN")

# --- LLM settings ------------------------------------------------------------
# Groq is OpenAI-compatible: we use the `openai` client and only swap base_url +
# model. `llama-3.3-70b-versatile` has solid tool use on the free tier.
# Fast alternative: "llama-3.1-8b-instant".
LLM_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "llama-3.3-70b-versatile"
TEMPERATURE = 0.7

# --- Agent loop --------------------------------------------------------------
# Safety cap on how many model<->tool round-trips a single user turn may take.
MAX_TOOL_STEPS = 5

# --- Domain defaults ---------------------------------------------------------
CURRENCY = "ils"


def require_llm_key():
    """Fail fast with a friendly message if the LLM key is missing."""
    if not LLM_API_KEY:
        raise SystemExit(
            "LLM_API_KEY is not set.\n"
            "Copy .env.example to .env and add your Groq API key "
            "(get one free at https://console.groq.com)."
        )
