import yfinance as yf
import pandas as pd
from config import TICKER, SHORT_WINDOW, LONG_WINDOW
from main import moving_average_strategy

STARTING_CAPITAL = 10_000.0
PERIOD = "2y"


def fetch_prices(ticker: str, period: str) -> list[float]:
    data = yf.download(ticker, period=period, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data["Close"].dropna().tolist()


def backtest(prices: list[float], signals: list[str], capital: float) -> dict:
    cash = capital
    shares = 0
    trades = []

    for i in range(1, len(prices)):
        prev, curr = signals[i - 1], signals[i]
        price = prices[i]

        if prev != "buy" and curr == "buy" and cash > 0:
            shares = cash // price
            cost = shares * price
            cash -= cost
            trades.append({"type": "buy", "price": price, "shares": shares})

        elif prev == "buy" and curr != "buy" and shares > 0:
            proceeds = shares * price
            cash += proceeds
            entry = next(t for t in reversed(trades) if t["type"] == "buy")
            profit = proceeds - entry["shares"] * entry["price"]
            trades.append({"type": "sell", "price": price, "shares": shares, "profit": profit})
            shares = 0

    final_value = cash + shares * prices[-1]
    sell_trades = [t for t in trades if t["type"] == "sell"]
    wins = [t for t in sell_trades if t["profit"] > 0]

    return {
        "start_value": capital,
        "end_value": final_value,
        "profit": final_value - capital,
        "return_pct": (final_value - capital) / capital * 100,
        "num_trades": len(sell_trades),
        "win_rate": len(wins) / len(sell_trades) * 100 if sell_trades else 0,
        "best_trade": max((t["profit"] for t in sell_trades), default=0),
        "worst_trade": min((t["profit"] for t in sell_trades), default=0),
        "trades": trades,
    }


if __name__ == "__main__":
    print(f"Backtesting {TICKER} over {PERIOD} | "
          f"SMA({SHORT_WINDOW}/{LONG_WINDOW}) | "
          f"Capital: ${STARTING_CAPITAL:,.0f}\n")

    prices = fetch_prices(TICKER, PERIOD)
    signals = moving_average_strategy(prices)
    result = backtest(prices, signals, STARTING_CAPITAL)

    print(f"Start value  : ${result['start_value']:>10,.2f}")
    print(f"End value    : ${result['end_value']:>10,.2f}")
    print(f"Profit/Loss  : ${result['profit']:>+10,.2f}")
    print(f"Return       : {result['return_pct']:>+9.2f}%")
    print(f"Trades       : {result['num_trades']}")
    print(f"Win rate     : {result['win_rate']:.1f}%")
    print(f"Best trade   : ${result['best_trade']:>+10,.2f}")
    print(f"Worst trade  : ${result['worst_trade']:>+10,.2f}")
