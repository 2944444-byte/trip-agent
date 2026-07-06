import json
from datetime import date

from openai import OpenAI

import config
from skills.loader import skills_prompt
from tools import AVAILABLE_TOOLS, TOOLS

config.require_llm_key()

client = OpenAI(base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY)

SYSTEM_PROMPT = f"""You are a travel planning assistant.
Today's date is {date.today().isoformat()}.
You help users plan trips: flights, hotels, budgets, and simple itineraries.

Rules:
- Tools: `search_flights` for LIVE flights and `search_hotels` for LIVE hotels.
  Use them whenever the user needs real options or prices. Do NOT invent results.
- Before searching flights you need origin, destination and a departure date
  (YYYY-MM-DD). Before searching hotels you need city, check-in and check-out
  dates. If something is missing, ask ONE short, specific follow-up first.
- Capture the user's preferences and pass them through; don't guess ones they
  didn't state. Flights: return date, cabin, stops, refundable, baggage, airline,
  budget. Hotels: guests, rooms, room type, budget, breakfast, cancellation, rating.
- Results include the details travelers care about — baggage/refund for flights,
  breakfast/cancellation/rating for hotels. Call these out explicitly.
- BOOKING LINKS: only ever share the exact `booking_link.url` returned by a tool,
  and only when `booking_link.verified` is true. NEVER write, guess, or modify a
  URL yourself. If a link isn't verified, say a verified link isn't available.
- After tool results, summarize clearly; when a budget was given, say which options
  fit it. Note the currency shown (it may not be ILS).
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
    seen_calls = {}

    for step in range(max_steps):
        force_answer = step == max_steps - 1
        response = client.chat.completions.create(
            model=config.MODEL,
            messages=messages,
            tools=TOOLS,
            tool_choice="none" if force_answer else "auto",
            temperature=config.TEMPERATURE,
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            return msg.content

        for tool_call in msg.tool_calls:
            key = (tool_call.function.name, tool_call.function.arguments)
            if key in seen_calls:
                content = seen_calls[key]
                print(f"  [tool] {tool_call.function.name} (repeat — using cached result)")
            else:
                content = json.dumps(_execute_tool_call(tool_call), default=str)
                seen_calls[key] = content
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": content,
            })

    return "I couldn't complete that search in time — please try again."


def main():
    skills_text, skill_names = skills_prompt()
    system_prompt = SYSTEM_PROMPT + skills_text

    messages = [{"role": "system", "content": system_prompt}]
    print("Travel Agent — type 'exit' to quit.")
    if skill_names:
        print(f"Loaded skills: {', '.join(skill_names)}")
    print()
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
