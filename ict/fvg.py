"""Fair Value Gaps (FVG) - three-candle price imbalances.

A bullish FVG exists when candle 3's low is above candle 1's high: the
impulsive middle candle left a gap of one-sided (buy) orders. Price commonly
retraces to "rebalance" the gap before continuing. Bearish is the mirror.
"""
from dataclasses import dataclass

import pandas as pd

from config import MIN_FVG_SIZE


@dataclass
class FairValueGap:
    index: int            # bar index of the middle (displacement) candle
    top: float
    bottom: float
    direction: str        # "bullish" | "bearish"
    filled_at: int | None = None   # bar that fully rebalanced the gap
    touched_at: int | None = None  # first bar that traded back into the gap

    @property
    def size(self) -> float:
        return self.top - self.bottom

    @property
    def midpoint(self) -> float:
        """Consequent encroachment - the 50% level ICT treats as the key react point."""
        return (self.top + self.bottom) / 2


def find_fair_value_gaps(df: pd.DataFrame,
                         min_size: float = MIN_FVG_SIZE) -> list[FairValueGap]:
    gaps: list[FairValueGap] = []
    highs, lows = df["high"].values, df["low"].values

    for i in range(1, len(df) - 1):
        # bullish: candle after the impulse never traded down to candle before it
        if lows[i + 1] > highs[i - 1]:
            gap = FairValueGap(i, float(lows[i + 1]), float(highs[i - 1]), "bullish")
            if gap.size >= min_size:
                gaps.append(gap)
        # bearish: candle after the impulse never traded up to candle before it
        if highs[i + 1] < lows[i - 1]:
            gap = FairValueGap(i, float(lows[i - 1]), float(highs[i + 1]), "bearish")
            if gap.size >= min_size:
                gaps.append(gap)

    _track_fills(df, gaps)
    return gaps


def _track_fills(df: pd.DataFrame, gaps: list[FairValueGap]) -> None:
    highs, lows = df["high"].values, df["low"].values
    for gap in gaps:
        for i in range(gap.index + 2, len(df)):
            if gap.direction == "bullish":
                if gap.touched_at is None and lows[i] < gap.top:
                    gap.touched_at = i
                if lows[i] <= gap.bottom:
                    gap.filled_at = i
                    break
            else:
                if gap.touched_at is None and highs[i] > gap.bottom:
                    gap.touched_at = i
                if highs[i] >= gap.top:
                    gap.filled_at = i
                    break
