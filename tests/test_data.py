import numpy as np
import pandas as pd
import yfinance

from data import fetch_ohlc


def fake_yf_frame() -> pd.DataFrame:
    """Shape a frame exactly like yf.download returns for one ticker:
    MultiIndex (field, symbol) columns and an exchange-local tz index."""
    index = pd.date_range("2026-07-06 09:30", periods=10, freq="5min",
                          tz="America/New_York")
    close = 44_000 + np.arange(10) * 5.0
    frame = pd.DataFrame({
        ("Open", "^DJI"): close - 3,
        ("High", "^DJI"): close + 6,
        ("Low", "^DJI"): close - 8,
        ("Close", "^DJI"): close,
        ("Volume", "^DJI"): np.full(10, 1_000_000.0),
    }, index=index)
    frame.columns = pd.MultiIndex.from_tuples(frame.columns)
    # yfinance pads the last bar with NaN while it's still forming
    frame.iloc[-1, frame.columns.get_loc(("Close", "^DJI"))] = np.nan
    return frame


def test_fetch_ohlc_normalises_yfinance_output(monkeypatch):
    monkeypatch.setattr(yfinance, "download",
                        lambda *a, **k: fake_yf_frame())
    df = fetch_ohlc("^DJI")

    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert str(df.index.tz) == "UTC"
    assert len(df) == 9            # NaN in-progress bar dropped
    assert df["high"].iloc[0] == 44_006.0
    # 09:30 New York in July == 13:30 UTC
    assert df.index[0].hour == 13 and df.index[0].minute == 30


def test_fetch_ohlc_raises_on_empty(monkeypatch):
    monkeypatch.setattr(yfinance, "download",
                        lambda *a, **k: pd.DataFrame())
    try:
        fetch_ohlc("^DJI")
        assert False, "expected RuntimeError on empty download"
    except RuntimeError as exc:
        assert "no data" in str(exc)
