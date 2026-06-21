"""Bot 2 — Signal explainer (Layer 4: system prompt + few-shot examples).

Single-purpose bot. Heavy use of a system prompt and example turns to lock
the output format exactly, with no training required.
"""
import anthropic
from market import TICKER, SHORT_WINDOW, LONG_WINDOW, fetch_prices, moving_average_strategy

MODEL = "claude-sonnet-4-6"
client = anthropic.Anthropic()

SYSTEM = """You explain moving-average crossover trading signals in plain English.
Answer in exactly three short sentences: (1) why the signal fired, (2) what the
recent price action suggests, (3) one risk to watch. Never promise profits."""

# Few-shot example shapes the format precisely (the Layer-4 technique).
EXAMPLES = [
    {
        "role": "user",
        "content": "AAPL | price $190.00 | short MA $192.00 | long MA $188.00 | signal BUY",
    },
    {
        "role": "assistant",
        "content": (
            "The 10-day average rose above the 50-day average, which triggers a BUY. "
            "Recent closes have trended upward, hinting at short-term momentum. "
            "Watch for a false breakout — crossovers can whipsaw in choppy markets."
        ),
    },
]


def explain_latest() -> str:
    prices = fetch_prices()
    signals = moving_average_strategy(prices)
    short_ma = sum(prices[-SHORT_WINDOW:]) / SHORT_WINDOW
    long_ma = sum(prices[-LONG_WINDOW:]) / LONG_WINDOW
    summary = (
        f"{TICKER} | price ${prices[-1]:.2f} | short MA ${short_ma:.2f} "
        f"| long MA ${long_ma:.2f} | signal {signals[-1].upper()}"
    )

    resp = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=SYSTEM,
        messages=[*EXAMPLES, {"role": "user", "content": summary}],
    )
    return next((b.text for b in resp.content if b.type == "text"), "")


if __name__ == "__main__":
    print(explain_latest())
