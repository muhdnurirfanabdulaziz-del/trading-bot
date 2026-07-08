"""Liquidity pools and liquidity sweeps.

- Buy-side liquidity (BSL) rests *above* swing highs / equal highs, where
  short-sellers keep stop-losses. Price is drawn up into it.
- Sell-side liquidity (SSL) rests *below* swing lows / equal lows, where
  long-traders keep stop-losses. Price is drawn down into it.
- A sweep (stop hunt / liquidity grab) is a wick through a pool followed by
  a close back on the original side - a classic reversal fingerprint.
"""
from dataclasses import dataclass, field

import pandas as pd

from config import EQUAL_LEVEL_TOLERANCE, SWING_LOOKBACK
from ict.structure import find_swings


@dataclass
class LiquidityPool:
    price: float          # the level stops sit behind
    side: str             # "buy_side" (above highs) | "sell_side" (below lows)
    indices: list = field(default_factory=list)  # swing bars forming the pool
    swept_at: int | None = None                  # bar index of the sweep, if any

    @property
    def strength(self) -> int:
        """Equal highs/lows stack more stops -> stronger magnet."""
        return len(self.indices)


def find_liquidity_pools(df: pd.DataFrame,
                         tolerance: float = EQUAL_LEVEL_TOLERANCE,
                         lookback: int = SWING_LOOKBACK) -> list[LiquidityPool]:
    """Cluster swing highs into buy-side pools and swing lows into sell-side
    pools; swings within `tolerance` points merge into one (equal highs/lows)."""
    swings = find_swings(df, lookback)
    pools: list[LiquidityPool] = []

    for kind, side in (("high", "buy_side"), ("low", "sell_side")):
        for s in (s for s in swings if s.kind == kind):
            merged = False
            for pool in pools:
                if pool.side == side and abs(pool.price - s.price) <= tolerance:
                    pool.indices.append(s.index)
                    # the pool sits behind the extreme of the cluster
                    pool.price = max(pool.price, s.price) if kind == "high" \
                        else min(pool.price, s.price)
                    merged = True
                    break
            if not merged:
                pools.append(LiquidityPool(s.price, side, [s.index]))

    return pools


def find_liquidity_sweeps(df: pd.DataFrame,
                          pools: list[LiquidityPool]) -> list[LiquidityPool]:
    """Mark pools whose level was wicked through but where the candle closed
    back on the original side (stops harvested, move rejected)."""
    swept: list[LiquidityPool] = []
    for pool in pools:
        start = max(pool.indices) + 1
        for i in range(start, len(df)):
            h, l, c = (float(df["high"].iloc[i]), float(df["low"].iloc[i]),
                       float(df["close"].iloc[i]))
            if pool.side == "buy_side" and h > pool.price and c < pool.price:
                pool.swept_at = i
                swept.append(pool)
                break
            if pool.side == "sell_side" and l < pool.price and c > pool.price:
                pool.swept_at = i
                swept.append(pool)
                break
    return swept
