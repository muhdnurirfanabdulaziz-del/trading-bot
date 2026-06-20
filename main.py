import yfinance as yf
import pandas as pd
from config import TICKER, SHORT_WINDOW, LONG_WINDOW


def fetch_prices(ticker: str, period: str = "6mo") -> list[float]:
    data = yf.download(ticker, period=period, progress=False)
    return data["Close"].dropna().tolist()


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


if __name__ == "__main__":
    print(f"Fetching 6 months of {TICKER} prices...")
    prices = fetch_prices(TICKER)
    signals = moving_average_strategy(prices)

    current_signal = signals[-1]
    print(f"Latest price : ${prices[-1]:.2f}")
    print(f"Signal       : {current_signal.upper()}")
    print()
    print("Last 5 signals:")
    for price, signal in zip(prices[-5:], signals[-5:]):
        print(f"  ${price:.2f}  ->  {signal}")
