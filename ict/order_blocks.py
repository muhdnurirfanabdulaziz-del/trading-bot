"""Order Blocks (OB) - the footprint of institutional accumulation/distribution.

A bullish OB is the last down-close candle before a displacement move up
(institutions filled longs into that candle's selling). A bearish OB is the
last up-close candle before a displacement move down. The zone is the
candle's full range; a revisit of the zone is a mitigation and a potential
entry in the direction of the displacement.
"""
from dataclasses import dataclass

import pandas as pd

from config import DISPLACEMENT_FACTOR


@dataclass
class OrderBlock:
    index: int            # bar index of the OB candle
    top: float
    bottom: float
    direction: str        # "bullish" | "bearish"
    mitigated_at: int | None = None  # first bar that traded back into the zone
    invalidated_at: int | None = None  # bar that closed through the zone

    @property
    def midpoint(self) -> float:
        return (self.top + self.bottom) / 2


def find_order_blocks(df: pd.DataFrame,
                      displacement_factor: float = DISPLACEMENT_FACTOR,
                      span: int = 3) -> list[OrderBlock]:
    """An OB candle must be followed within `span` bars by displacement -
    a net move of at least `displacement_factor` x average candle range that
    also runs beyond the OB candle's extreme."""
    opens, closes = df["open"].values, df["close"].values
    highs, lows = df["high"].values, df["low"].values
    avg_range = float((df["high"] - df["low"]).mean())
    threshold = displacement_factor * avg_range

    blocks: list[OrderBlock] = []
    for i in range(len(df) - span):
        end = min(i + span, len(df) - 1)
        # bullish OB: down candle, then price displaces up through its high
        if closes[i] < opens[i]:
            move = float(closes[i + 1: end + 1].max() - closes[i])
            if move >= threshold and closes[i + 1: end + 1].max() > highs[i]:
                blocks.append(OrderBlock(i, float(highs[i]), float(lows[i]),
                                         "bullish"))
        # bearish OB: up candle, then price displaces down through its low
        if closes[i] > opens[i]:
            move = float(closes[i] - closes[i + 1: end + 1].min())
            if move >= threshold and closes[i + 1: end + 1].min() < lows[i]:
                blocks.append(OrderBlock(i, float(highs[i]), float(lows[i]),
                                         "bearish"))

    _track_mitigation(df, blocks, span)
    return blocks


def _track_mitigation(df: pd.DataFrame, blocks: list[OrderBlock],
                      span: int) -> None:
    highs, lows, closes = df["high"].values, df["low"].values, df["close"].values
    for ob in blocks:
        for i in range(ob.index + span, len(df)):
            if ob.direction == "bullish":
                if ob.mitigated_at is None and lows[i] <= ob.top:
                    ob.mitigated_at = i
                if closes[i] < ob.bottom:
                    ob.invalidated_at = i
                    break
            else:
                if ob.mitigated_at is None and highs[i] >= ob.bottom:
                    ob.mitigated_at = i
                if closes[i] > ob.top:
                    ob.invalidated_at = i
                    break
