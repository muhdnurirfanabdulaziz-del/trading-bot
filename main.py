import pandas as pd
from config import TICKER, SHORT_WINDOW, LONG_WINDOW


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
    print(f"Running strategy for {TICKER} "
          f"(short={SHORT_WINDOW}, long={LONG_WINDOW})")
