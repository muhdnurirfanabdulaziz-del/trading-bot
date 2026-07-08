"""OHLC data for the bot.

`load_csv` takes any broker/TradingView export with time,open,high,low,close
columns. `sample_us30` synthesises a realistic US30 M5 session so everything
runs offline on a laptop with no data feed.
"""
import numpy as np
import pandas as pd


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    time_col = next(c for c in df.columns if c in ("time", "date", "datetime",
                                                   "timestamp"))
    df[time_col] = pd.to_datetime(df[time_col], utc=True)
    df = df.set_index(time_col).sort_index()
    return df[["open", "high", "low", "close"]].astype(float)


def sample_us30(seed: int = 7) -> pd.DataFrame:
    """One trading day of synthetic US30 M5 candles (00:00-16:00 New York),
    with an engineered London-session stop hunt and reversal so the ICT
    detectors have something to find."""
    rng = np.random.default_rng(seed)
    index = pd.date_range("2026-07-06 04:00", periods=192, freq="5min",
                          tz="UTC")  # 00:00-16:00 New York (EDT)

    n = len(index)
    drift = np.zeros(n)
    vol = np.full(n, 8.0)

    # Asia: quiet range. London (bars 24-60): sell-off into sell-side
    # liquidity, sweep, then displacement up. NY AM (bars 102-132): trend up.
    drift[24:44] = -4.0
    drift[44:60] = 6.0
    vol[24:60] = 14.0
    drift[102:132] = 3.5
    vol[102:132] = 16.0

    steps = drift + rng.normal(0, vol)
    close = 44_000 + np.cumsum(steps)
    open_ = np.concatenate(([44_000.0], close[:-1]))
    spread_hi = np.abs(rng.normal(0, vol * 0.6))
    spread_lo = np.abs(rng.normal(0, vol * 0.6))
    high = np.maximum(open_, close) + spread_hi
    low = np.minimum(open_, close) - spread_lo

    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close},
        index=index,
    ).round(1)
