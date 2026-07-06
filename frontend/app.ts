// Chat UI logic (TypeScript source). Compile to app.js with `tsc` (see tsconfig.json).
// The browser loads the compiled app.js, not this file.

interface ChatResponse {
  reply: string;
}

const chat = document.getElementById("chat") as HTMLElement;
const form = document.getElementById("form") as HTMLFormElement;
const input = document.getElementById("input") as HTMLTextAreaElement;
const send = document.getElementById("send") as HTMLButtonElement;
const resetBtn = document.getElementById("reset") as HTMLButtonElement;

function escapeHtml(s: string): string {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function linkify(s: string): string {
  return s.replace(
    /(https?:\/\/[^\s<]+)/g,
    '<a href="$1" target="_blank" rel="noopener">$1</a>'
  );
}

function addMessage(text: string, who: "user" | "agent"): HTMLElement {
  const el = document.createElement("div");
  el.className = `msg ${who}`;
  el.innerHTML = who === "agent" ? linkify(escapeHtml(text)) : escapeHtml(text);
  chat.appendChild(el);
  chat.scrollTop = chat.scrollHeight;
  return el;
}

async function sendMessage(text: string): Promise<void> {
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
    const data: ChatResponse = await res.json();
    typing.classList.remove("typing");
    typing.innerHTML = linkify(escapeHtml(data.reply || "(no response)"));
  } catch {
    typing.classList.remove("typing");
    typing.textContent = "Network error — is the server running?";
  } finally {
    send.disabled = false;
    input.disabled = false;
    input.focus();
    chat.scrollTop = chat.scrollHeight;
  }
}

form.addEventListener("submit", (e: SubmitEvent) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  input.style.height = "auto";
  void sendMessage(text);
});

input.addEventListener("keydown", (e: KeyboardEvent) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

input.addEventListener("input", () => {
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 140)}px`;
});

document.querySelectorAll<HTMLButtonElement>(".example").forEach((btn) => {
  btn.addEventListener("click", () => {
    input.value = btn.textContent ?? "";
    input.focus();
  });
});

resetBtn.addEventListener("click", async () => {
  await fetch("/api/reset", { method: "POST" });
  chat.querySelectorAll(".msg").forEach((m) => m.remove());
});

input.focus();
