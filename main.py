import json
from datetime import date

from openai import OpenAI

import config
from tools import AVAILABLE_TOOLS, TOOLS

config.require_llm_key()

client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)

SYSTEM_PROMPT = f"""You are a travel planning assistant.
Today's date is {date.today().isoformat()}.
You help users plan trips: flights, hotels, budgets, and simple itineraries.

Rules:
- You have a tool, search_flights, for looking up flight options. Use it whenever
  the user needs real flight options, times, or prices. Do NOT invent flights.
- Before calling the tool, make sure you have origin, destination and a date.
  If any is missing, ask ONE short, specific follow-up question first.
- After you get tool results, summarize them clearly for the user and, when a
  budget was given, say which options fit it.
- Flight prices are cached (from recent searches), not live seat availability. Be
  honest that they indicate what fits a budget but don't guarantee a bookable seat.
- Amounts are in ILS unless the user says otherwise.
- You do NOT yet have a hotel tool. If asked about hotels, say so honestly.
"""


def _execute_tool_call(tool_call):
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        return {"error": f"could not parse tool arguments: {e}"}

    func = AVAILABLE_TOOLS.get(name)
    if func is None:
        return {"error": f"unknown tool: {name}"}

    print(f"  [tool] {name}({args})")
    try:
        return func(**args)
    except Exception as e:  # tool bugs shouldn't crash the conversation
        return {"error": str(e)}


def run_agent_turn(messages, max_steps=config.MAX_TOOL_STEPS):
    for _ in range(max_steps):
        response = client.chat.completions.create(
            model=config.MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=config.TEMPERATURE,
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            return msg.content

        for tool_call in msg.tool_calls:
            result = _execute_tool_call(tool_call)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, default=str),
            })

    return "Stopped after too many tool steps."


def main():
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("Travel Agent — type 'exit' to quit.\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        if not user_input:
            continue
        messages.append({"role": "user", "content": user_input})
        reply = run_agent_turn(messages)
        print(f"\nAgent: {reply}\n")


if __name__ == "__main__":
    main()
