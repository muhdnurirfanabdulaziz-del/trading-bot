"""Standalone market helpers for the ai_bots package.

Self-contained copy so the bots never depend on the parent trading-bot
project. Edit the constants here to change ticker / window sizes.
"""
import requests
import pandas as pd

TICKER = "AAPL"
SHORT_WINDOW = 10
LONG_WINDOW = 50


def fetch_prices(ticker: str = TICKER, period_days: int = 60) -> list[float]:
    """Fetch daily closing prices from Yahoo Finance (no API key needed)."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?interval=1d&range={period_days}d"
    )
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    resp.raise_for_status()
    closes = resp.json()["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    return [p for p in closes if p is not None]


def moving_average_strategy(prices: list[float]) -> list[str]:
    """Return a signal ('buy', 'sell', 'hold') for each price point."""
    series = pd.Series(prices)
    short_ma = series.rolling(SHORT_WINDOW).mean()
    long_ma = series.rolling(LONG_WINDOW).mean()

    signals = []
    for i in range(len(prices)):
        if short_ma[i] > long_ma[i]:
            signals.append("buy")
        elif short_ma[i] < long_ma[i]:
            signals.append("sell")
        else:
            signals.append("hold")
    return signals
