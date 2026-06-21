"""Bot 1 — Conversational assistant (Layer 1: Claude API chatbot).

A multi-turn chat REPL with a custom personality. Demonstrates the simplest
AI layer: talk to Claude with your own system prompt and conversation memory.
"""
import anthropic

MODEL = "claude-sonnet-4-6"

SYSTEM = """You are TradeBuddy, a friendly assistant for a hobbyist running a
moving-average crossover trading bot. Explain things simply and concisely.
This is for paper-trading and education only — when the user asks about real
money, remind them you don't give guaranteed financial advice."""

client = anthropic.Anthropic()


def main():
    messages = []
    print("TradeBuddy (Sonnet 4.6) — type 'quit' to exit.\n")
    while True:
        user = input("You: ").strip()
        if user.lower() in {"quit", "exit"}:
            break
        messages.append({"role": "user", "content": user})

        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM,
            messages=messages,
        )
        reply = next((b.text for b in resp.content if b.type == "text"), "")
        print(f"\nTradeBuddy: {reply}\n")
        messages.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
