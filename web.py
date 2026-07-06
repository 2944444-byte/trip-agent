"""Minimal web chat UI for the travel agent.

A thin Flask wrapper around the existing agent loop (`run_agent_turn`). It serves a
single self-contained chat page and a `/chat` JSON endpoint. Conversation state is
kept in-process for one local user — this is a simple demo UI, not a multi-user
server. Run it with:

    python web.py      # then open http://127.0.0.1:5000
"""
from flask import Flask, Response, jsonify, request

from main import SYSTEM_PROMPT, run_agent_turn
from skills.loader import skills_prompt

app = Flask(__name__)

# Compose the base prompt with the Markdown skills, same as the CLI does.
_SKILLS_TEXT, _SKILL_NAMES = skills_prompt()
_SYSTEM_PROMPT = SYSTEM_PROMPT + _SKILLS_TEXT


def _new_conversation():
    return [{"role": "system", "content": _SYSTEM_PROMPT}]


# Single-session conversation (local demo). /reset starts a fresh one.
conversation = _new_conversation()


@app.route("/")
def index():
    return Response(INDEX_HTML, mimetype="text/html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"reply": "Please type a message."})

    conversation.append({"role": "user", "content": message})
    try:
        reply = run_agent_turn(conversation)
    except Exception as e:  # never let the UI hang on a server error
        reply = f"Sorry — something went wrong: {e}"
    return jsonify({"reply": reply or "(no response)"})


@app.route("/reset", methods=["POST"])
def reset():
    global conversation
    conversation = _new_conversation()
    return jsonify({"ok": True})


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Travel Agent</title>
<style>
  :root { --bg:#0f172a; --panel:#111827; --user:#2563eb; --agent:#1f2937;
          --text:#e5e7eb; --muted:#94a3b8; --accent:#38bdf8; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
         background: var(--bg); color: var(--text); height:100vh; display:flex;
         flex-direction:column; }
  header { padding:14px 18px; background:linear-gradient(90deg,#1e3a8a,#0ea5e9);
           font-weight:600; font-size:18px; display:flex; align-items:center;
           justify-content:space-between; }
  header .sub { font-weight:400; font-size:12px; opacity:.85; }
  #reset { background:rgba(255,255,255,.15); border:none; color:#fff; cursor:pointer;
           padding:6px 12px; border-radius:8px; font-size:13px; }
  #reset:hover { background:rgba(255,255,255,.28); }
  #chat { flex:1; overflow-y:auto; padding:20px; display:flex; flex-direction:column;
          gap:12px; }
  .msg { max-width:min(720px, 85%); padding:11px 14px; border-radius:14px;
         line-height:1.5; white-space:pre-wrap; word-wrap:break-word; }
  .user { align-self:flex-end; background:var(--user); border-bottom-right-radius:4px; }
  .agent { align-self:flex-start; background:var(--agent); border-bottom-left-radius:4px; }
  .agent a { color:var(--accent); }
  .hint { align-self:center; color:var(--muted); font-size:13px; text-align:center;
          max-width:560px; }
  .hint code { background:#1e293b; padding:2px 6px; border-radius:6px; cursor:pointer; }
  .typing { color:var(--muted); font-style:italic; }
  form { display:flex; gap:10px; padding:14px; background:var(--panel);
         border-top:1px solid #1f2937; }
  #input { flex:1; resize:none; background:#0b1220; color:var(--text);
           border:1px solid #334155; border-radius:12px; padding:12px 14px;
           font-size:15px; font-family:inherit; max-height:140px; }
  #input:focus { outline:none; border-color:var(--accent); }
  #send { background:var(--accent); color:#00131f; border:none; border-radius:12px;
          padding:0 20px; font-weight:600; cursor:pointer; font-size:15px; }
  #send:disabled { opacity:.5; cursor:default; }
</style>
</head>
<body>
  <header>
    <div>✈️  Travel Agent <span class="sub">flights &amp; hotels</span></div>
    <button id="reset" title="Start over">Reset</button>
  </header>
  <div id="chat">
    <div class="hint">
      Ask about flights and hotels. Try:<br>
      <code>Direct flights from TLV to Athens on 2026-11-14, cheapest first.</code><br>
      <code>Hotel in Rome for 3 friends, 2026-11-07 to 2026-11-09, breakfast included.</code>
    </div>
  </div>
  <form id="form">
    <textarea id="input" rows="1" placeholder="Type your trip request…  (Enter to send, Shift+Enter for a new line)"></textarea>
    <button id="send" type="submit">Send</button>
  </form>
<script>
  const chat = document.getElementById('chat');
  const form = document.getElementById('form');
  const input = document.getElementById('input');
  const send = document.getElementById('send');

  function escapeHtml(s){ const d=document.createElement('div'); d.textContent=s; return d.innerHTML; }
  function linkify(s){ return s.replace(/(https?:\\/\\/[^\\s<]+)/g,
      '<a href="$1" target="_blank" rel="noopener">$1</a>'); }

  function addMessage(text, who){
    const el = document.createElement('div');
    el.className = 'msg ' + who;
    el.innerHTML = who === 'agent' ? linkify(escapeHtml(text)) : escapeHtml(text);
    chat.appendChild(el);
    chat.scrollTop = chat.scrollHeight;
    return el;
  }

  async function sendMessage(text){
    addMessage(text, 'user');
    const typing = addMessage('Agent is thinking…', 'agent');
    typing.classList.add('typing');
    send.disabled = true; input.disabled = true;
    try {
      const res = await fetch('/chat', { method:'POST',
        headers:{'Content-Type':'application/json'}, body: JSON.stringify({message:text}) });
      const data = await res.json();
      typing.classList.remove('typing');
      typing.innerHTML = linkify(escapeHtml(data.reply || '(no response)'));
    } catch (e) {
      typing.classList.remove('typing');
      typing.textContent = 'Network error — is the server running?';
    } finally {
      send.disabled = false; input.disabled = false; input.focus();
      chat.scrollTop = chat.scrollHeight;
    }
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = ''; input.style.height = 'auto';
    sendMessage(text);
  });

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  input.addEventListener('input', () => {
    input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 140) + 'px';
  });
  document.querySelectorAll('.hint code').forEach(c =>
    c.addEventListener('click', () => { input.value = c.textContent; input.focus(); }));

  document.getElementById('reset').addEventListener('click', async () => {
    await fetch('/reset', { method:'POST' });
    chat.querySelectorAll('.msg').forEach(m => m.remove());
  });

  input.focus();
</script>
</body>
</html>"""


if __name__ == "__main__":
    print("Travel Agent web UI -> http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
