"""FastAPI web server for the travel agent chat UI.

A thin wrapper around the existing agent loop (`run_agent_turn`). It serves the
static frontend (HTML/CSS/compiled TS) and a small JSON API. Conversation state is
kept in-process for one local user — a demo UI, not a multi-user server.

Run it with:

    uvicorn server:app --reload      # http://127.0.0.1:8000
    # or:  python server.py
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from main import SYSTEM_PROMPT, run_agent_turn
from skills.loader import skills_prompt

_FRONTEND = Path(__file__).resolve().parent / "frontend"

# Compose the base prompt with the Markdown skills, same as the CLI does.
_SYSTEM_PROMPT = SYSTEM_PROMPT + skills_prompt()[0]

app = FastAPI(title="Travel Agent")


def _new_conversation():
    return [{"role": "system", "content": _SYSTEM_PROMPT}]


# Single-session conversation (local demo). /api/reset starts a fresh one.
conversation = _new_conversation()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    message = (req.message or "").strip()
    if not message:
        return ChatResponse(reply="Please type a message.")

    conversation.append({"role": "user", "content": message})
    try:
        reply = run_agent_turn(conversation)
    except Exception as e:  # never let the UI hang on a server error
        reply = f"Sorry — something went wrong: {e}"
    return ChatResponse(reply=reply or "(no response)")


@app.post("/api/reset")
def reset() -> dict:
    global conversation
    conversation = _new_conversation()
    return {"ok": True}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_FRONTEND / "index.html")


# Serve styles.css, app.js, etc. Mounted last so it doesn't shadow the API routes.
app.mount("/static", StaticFiles(directory=_FRONTEND), name="static")


if __name__ == "__main__":
    import uvicorn

    print("Travel Agent web UI -> http://127.0.0.1:8080")
    uvicorn.run(app, host="127.0.0.1", port=8080)
