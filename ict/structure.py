"""Market structure: swing points, BOS, CHoCH and MSS.

Structure is mapped from confirmed swing highs/lows:

- BOS  (Break of Structure): price closes beyond the last swing point in the
  direction of the current trend -> continuation.
- CHoCH (Change of Character): price closes beyond the last swing point
  *against* the current trend -> first warning of a reversal.
- MSS  (Market Structure Shift): a CHoCH that follows a liquidity sweep or
  displacement; here we label the CHoCH candle that also closes beyond the
  swing with an expansion candle as MSS.
"""
from dataclasses import dataclass, field

import pandas as pd

from config import SWING_LOOKBACK


@dataclass
class Swing:
    index: int          # bar index of the swing extreme
    price: float
    kind: str           # "high" or "low"


@dataclass
class StructureEvent:
    index: int          # bar index where the break was confirmed (close beyond)
    price: float        # the swing level that broke
    kind: str           # "BOS" | "CHoCH" | "MSS"
    direction: str      # "bullish" | "bearish"


@dataclass
class StructureState:
    trend: str = "neutral"                      # "bullish" | "bearish" | "neutral"
    swings: list = field(default_factory=list)
    events: list = field(default_factory=list)


def find_swings(df: pd.DataFrame, lookback: int = SWING_LOOKBACK) -> list[Swing]:
    """Fractal swing points: a high (low) with `lookback` lower highs
    (higher lows) on each side."""
    highs, lows = df["high"].values, df["low"].values
    swings: list[Swing] = []
    for i in range(lookback, len(df) - lookback):
        window_h = highs[i - lookback: i + lookback + 1]
        window_l = lows[i - lookback: i + lookback + 1]
        if highs[i] == window_h.max() and (window_h < highs[i]).sum() == 2 * lookback:
            swings.append(Swing(i, float(highs[i]), "high"))
        if lows[i] == window_l.min() and (window_l > lows[i]).sum() == 2 * lookback:
            swings.append(Swing(i, float(lows[i]), "low"))
    swings.sort(key=lambda s: s.index)
    return swings


def analyze_structure(df: pd.DataFrame,
                      lookback: int = SWING_LOOKBACK) -> StructureState:
    """Walk the bars, tracking the last swing high/low and labelling breaks."""
    swings = find_swings(df, lookback)
    state = StructureState(swings=swings)

    closes = df["close"].values
    avg_range = float((df["high"] - df["low"]).mean())

    last_high: Swing | None = None
    last_low: Swing | None = None
    swing_iter = iter(swings)
    next_swing = next(swing_iter, None)

    for i in range(len(df)):
        # A swing only becomes known `lookback` bars after its extreme.
        while next_swing is not None and next_swing.index + lookback <= i:
            if next_swing.kind == "high":
                last_high = next_swing
            else:
                last_low = next_swing
            next_swing = next(swing_iter, None)

        close = closes[i]
        candle_range = float(df["high"].iloc[i] - df["low"].iloc[i])
        displaced = candle_range > 1.5 * avg_range

        if last_high is not None and close > last_high.price:
            direction = "bullish"
            if state.trend == "bullish":
                kind = "BOS"
            else:
                kind = "MSS" if displaced else "CHoCH"
            state.events.append(StructureEvent(i, last_high.price, kind, direction))
            state.trend = "bullish"
            last_high = None  # consumed; wait for a new swing high

        if last_low is not None and close < last_low.price:
            direction = "bearish"
            if state.trend == "bearish":
                kind = "BOS"
            else:
                kind = "MSS" if displaced else "CHoCH"
            state.events.append(StructureEvent(i, last_low.price, kind, direction))
            state.trend = "bearish"
            last_low = None

    return state
