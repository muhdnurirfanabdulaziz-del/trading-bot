"""ICT confluence strategy for US30.

A signal fires on a bar only when the pieces line up:

1. Kill zone     - the bar opens inside London Open or New York AM.
2. Narrative     - a liquidity pool was just swept (stop hunt), suggesting the
                   move against it is fuelled.
3. Structure     - a CHoCH/MSS (reversal) or BOS (continuation) confirms the
                   direction away from the swept pool.
4. Entry zone    - price is trading back into an unmitigated order block or
                   an unfilled fair value gap aligned with that direction.

Stops go behind the entry zone, targets at the opposite-side liquidity pool;
setups below MIN_RR are discarded.
"""
from dataclasses import dataclass

import pandas as pd

from config import MIN_RR
from ict.fvg import find_fair_value_gaps
from ict.killzones import active_kill_zone
from ict.liquidity import find_liquidity_pools, find_liquidity_sweeps
from ict.order_blocks import find_order_blocks
from ict.structure import analyze_structure


@dataclass
class Signal:
    index: int
    time: object
    direction: str        # "long" | "short"
    entry: float
    stop: float
    target: float
    kill_zone: str
    reasons: list

    @property
    def rr(self) -> float:
        risk = abs(self.entry - self.stop)
        return abs(self.target - self.entry) / risk if risk else 0.0


# How many bars a sweep or structure event stays "fresh" as confluence.
RECENT = 12


def generate_signals(df: pd.DataFrame, min_rr: float = MIN_RR) -> list[Signal]:
    """df needs columns open/high/low/close and a DatetimeIndex."""
    structure = analyze_structure(df)
    pools = find_liquidity_pools(df)
    sweeps = find_liquidity_sweeps(df, pools)
    gaps = find_fair_value_gaps(df)
    blocks = find_order_blocks(df)

    signals: list[Signal] = []

    for i in range(len(df)):
        zone = active_kill_zone(df.index[i])
        if zone is None:
            continue

        bar_low, bar_high = float(df["low"].iloc[i]), float(df["high"].iloc[i])
        close = float(df["close"].iloc[i])

        for direction in ("long", "short"):
            bullish = direction == "long"

            # 2. a sweep of the pool opposite our direction, recently
            sweep = next((p for p in sweeps if p.swept_at is not None
                          and 0 <= i - p.swept_at <= RECENT
                          and p.side == ("sell_side" if bullish else "buy_side")),
                         None)
            if sweep is None:
                continue

            # 3. structure agrees, confirmed by a recent event our way
            event = next((e for e in reversed(structure.events)
                          if e.index <= i and i - e.index <= RECENT
                          and e.direction == ("bullish" if bullish else "bearish")),
                         None)
            if event is None:
                continue

            # 4. bar taps an aligned, still-valid OB or FVG
            zone_hit = None
            for ob in blocks:
                if (ob.direction == ("bullish" if bullish else "bearish")
                        and ob.index < i
                        and (ob.invalidated_at is None or ob.invalidated_at > i)
                        and bar_low <= ob.top and bar_high >= ob.bottom):
                    zone_hit = ("order block", ob.top, ob.bottom)
                    break
            if zone_hit is None:
                for gap in gaps:
                    if (gap.direction == ("bullish" if bullish else "bearish")
                            and gap.index < i
                            and (gap.filled_at is None or gap.filled_at > i)
                            and bar_low <= gap.top and bar_high >= gap.bottom):
                        zone_hit = ("fair value gap", gap.top, gap.bottom)
                        break
            if zone_hit is None:
                continue

            zone_name, zone_top, zone_bottom = zone_hit
            entry = close
            stop = zone_bottom - 1.0 if bullish else zone_top + 1.0

            # target: nearest unswept liquidity on the opposite side
            if bullish:
                targets = [p.price for p in pools
                           if p.side == "buy_side" and p.swept_at is None
                           and p.price > entry]
                target = min(targets) if targets else None
            else:
                targets = [p.price for p in pools
                           if p.side == "sell_side" and p.swept_at is None
                           and p.price < entry]
                target = max(targets) if targets else None
            if target is None:
                continue

            sig = Signal(
                index=i, time=df.index[i], direction=direction,
                entry=entry, stop=stop, target=target, kill_zone=zone,
                reasons=[
                    f"{'sell-side' if bullish else 'buy-side'} liquidity swept "
                    f"at {sweep.price:.0f} (bar {sweep.swept_at})",
                    f"{event.kind} {event.direction} through {event.price:.0f}",
                    f"price tapped {'bullish' if bullish else 'bearish'} "
                    f"{zone_name} {zone_bottom:.0f}-{zone_top:.0f}",
                ],
            )
            if sig.rr >= min_rr:
                signals.append(sig)

    return signals
