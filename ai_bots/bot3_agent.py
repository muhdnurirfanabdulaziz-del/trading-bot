"""Bot 3 — Tool-using agent (Layer 2: agent + tools).

Claude decides when to call your functions. It can fetch live prices and run
the strategy itself, then answer in natural language. Uses a manual agentic
loop (no beta features required).
"""
import json
import anthropic
from market import TICKER, fetch_prices, moving_average_strategy

MODEL = "claude-sonnet-4-6"
client = anthropic.Anthropic()

TOOLS = [
    {
        "name": "fetch_prices",
        "description": "Fetch recent daily closing prices for a stock ticker. "
                       "Call this when you need price data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Ticker symbol, e.g. AAPL"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "run_strategy",
        "description": "Run the moving-average crossover strategy on a list of "
                       "prices and return the latest signal (buy/sell/hold).",
        "input_schema": {
            "type": "object",
            "properties": {
                "prices": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Closing prices, oldest first",
                },
            },
            "required": ["prices"],
        },
    },
]


def run_tool(name: str, tool_input: dict) -> str:
    if name == "fetch_prices":
        prices = fetch_prices(tool_input.get("ticker", TICKER))
        return json.dumps({"prices": [round(p, 2) for p in prices]})
    if name == "run_strategy":
        signals = moving_average_strategy(tool_input["prices"])
        return json.dumps({"latest_signal": signals[-1], "points": len(signals)})
    return json.dumps({"error": f"unknown tool {name}"})


def ask(question: str) -> str:
    messages = [{"role": "user", "content": question}]
    while True:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )
        if resp.stop_reason != "tool_use":
            return next((b.text for b in resp.content if b.type == "text"), "")

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": run_tool(block.name, block.input),
                })
        messages.append({"role": "user", "content": results})


if __name__ == "__main__":
    print(ask("What's the current moving-average signal for AAPL, and why?"))
