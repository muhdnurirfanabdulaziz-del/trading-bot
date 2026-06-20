import yfinance as yf
import pandas as pd
from config import TICKER, SHORT_WINDOW, LONG_WINDOW, VOLUME_WINDOW, MACD_FAST, MACD_SLOW, MACD_SIGNAL


def fetch_data(ticker: str, period: str = "6mo") -> tuple[list[float], list[float]]:
    data = yf.download(ticker, period=period, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data = data.dropna(subset=["Close", "Volume"])
    return data["Close"].tolist(), data["Volume"].tolist()


def compute_macd(prices: pd.Series) -> tuple[pd.Series, pd.Series]:
    fast_ema = prices.ewm(span=MACD_FAST, adjust=False).mean()
    slow_ema = prices.ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    return macd_line, signal_line


def moving_average_strategy(prices: list[float], volumes: list[float]) -> list[str]:
    """Return a signal ('buy', 'sell', 'hold') for each price point.

    All three conditions must agree to emit buy/sell:
      - SMA crossover (short > long)
      - Volume above its rolling average
      - MACD line above its signal line
    """
    price_series = pd.Series(prices)
    short_ma = price_series.rolling(SHORT_WINDOW).mean()
    long_ma = price_series.rolling(LONG_WINDOW).mean()

    volume_series = pd.Series(volumes)
    volume_ma = volume_series.rolling(VOLUME_WINDOW).mean()

    macd_line, signal_line = compute_macd(price_series)

    signals = []
    for i in range(len(prices)):
        above_volume = volume_series[i] > volume_ma[i]
        macd_bullish = macd_line[i] > signal_line[i]
        if short_ma[i] > long_ma[i] and above_volume and macd_bullish:
            signals.append("buy")
        elif short_ma[i] < long_ma[i] and above_volume and not macd_bullish:
            signals.append("sell")
        else:
            signals.append("hold")
    return signals


if __name__ == "__main__":
    print(f"Fetching 6 months of {TICKER} data...")
    prices, volumes = fetch_data(TICKER)
    signals = moving_average_strategy(prices, volumes)

    price_series = pd.Series(prices)
    macd_line, signal_line = compute_macd(price_series)

    current_signal = signals[-1]
    print(f"Latest price  : ${prices[-1]:.2f}")
    print(f"Latest volume : {volumes[-1]:,.0f}")
    print(f"MACD          : {macd_line.iloc[-1]:.4f}  |  Signal: {signal_line.iloc[-1]:.4f}")
    print(f"Signal        : {current_signal.upper()}")
    print()
    print("Last 5 signals:")
    for price, volume, macd, sig, signal in zip(
        prices[-5:], volumes[-5:], macd_line.iloc[-5:], signal_line.iloc[-5:], signals[-5:]
    ):
        print(f"  ${price:.2f}  vol={volume:,.0f}  macd={macd:.4f}/{sig:.4f}  ->  {signal}")
