import requests
from config import TICKER


def fetch_prices(period_days: int = 60) -> list[float]:
    """Fetch daily closing prices for TICKER from Yahoo Finance."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{TICKER}"
        f"?interval=1d&range={period_days}d"
    )
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
    return [p for p in closes if p is not None]
