"use strict";
// Compiled from app.ts (target ES2017). Regenerate with `tsc` — see tsconfig.json.
const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("input");
const send = document.getElementById("send");
const resetBtn = document.getElementById("reset");

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function linkify(s) {
  return s.replace(
    /(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noopener">$1</a>'
  );
}

function addMessage(text, who) {
  const el = document.createElement("div");
  el.className = `msg ${who}`;
  el.innerHTML = who === "agent" ? linkify(escapeHtml(text)) : escapeHtml(text);
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
  return el;
}

async function sendMessage(text) {
  addMessage(text, "user");
  const typing = addMessage("Agent is thinking…", "agent");
  typing.classList.add("typing");
  send.disabled = true;
  input.disabled = true;
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    typing.classList.remove("typing");
    typing.innerHTML = linkify(escapeHtml(data.reply || "(no response)"));
  } catch (_a) {
    typing.classList.remove("typing");
    typing.textContent = "Network error — is the server running?";
  } finally {
    send.disabled = false;
    input.disabled = false;
    input.focus();
    chat.scrollTop = chat.scrollHeight;
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  input.style.height = "auto";
  void sendMessage(text);
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
});

document.querySelectorAll(".example").forEach((btn) => {
  btn.addEventListener("click", () => {
    var _a;
    input.value = (_a = btn.textContent) !== null && _a !== void 0 ? _a : "";
    input.focus();
  });
});

resetBtn.addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  chat.querySelectorAll(".msg").forEach((m) => m.remove());
});

input.focus();
