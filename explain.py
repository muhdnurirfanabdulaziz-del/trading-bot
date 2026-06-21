import anthropic
from config import TICKER, SHORT_WINDOW, LONG_WINDOW

client = anthropic.Anthropic()


def explain_signal(prices: list[float], signals: list[str]) -> str:
    """Ask Claude to explain the latest trading signal in plain English."""
    latest_signal = signals[-1]
    recent_prices = prices[-max(LONG_WINDOW, 10):]
    short_ma = sum(prices[-SHORT_WINDOW:]) / SHORT_WINDOW
    long_ma = sum(prices[-LONG_WINDOW:]) / LONG_WINDOW

    prompt = f"""You are a trading assistant explaining a moving-average crossover strategy signal.

Ticker: {TICKER}
Latest closing price: ${prices[-1]:.2f}
Short MA ({SHORT_WINDOW}-day): ${short_ma:.2f}
Long MA ({LONG_WINDOW}-day): ${long_ma:.2f}
Signal: {latest_signal.upper()}
Recent prices (last {len(recent_prices)} days): {[round(p, 2) for p in recent_prices]}

Explain in 2-3 plain-English sentences why this signal was generated, what the price action suggests, and one key risk to watch."""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text
