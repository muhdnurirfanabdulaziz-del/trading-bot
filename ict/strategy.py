"""ICT confluence strategy for US30.

Hard requirements for a signal on a bar:

1. Kill zone     - the bar opens inside London Open or New York AM.
2. Entry zone    - price is trading back into an unmitigated order block or
                   an unfilled fair value gap, which sets the direction.

Plus at least MIN_CONFLUENCE of the two narrative conditions:

3. Sweep         - a liquidity pool opposite the trade direction was swept
                   recently (stop hunt fuels the move).
4. Structure     - a recent BOS/CHoCH/MSS confirms the direction.

Stops go behind the entry zone. Targets prefer the nearest opposing
liquidity pool; with none in reach, a fixed MIN_RR target is used.
Setups below MIN_RR are discarded, and the same direction won't fire
again within SIGNAL_COOLDOWN_BARS.
"""
from dataclasses import dataclass

import pandas as pd

from config import (
    MIN_CONFLUENCE,
    MIN_RR,
    SIGNAL_COOLDOWN_BARS,
    SIGNAL_FRESHNESS_BARS,
)
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
    confluence: int       # narrative conditions met (sweep, structure)
    reasons: list

    @property
    def rr(self) -> float:
        risk = abs(self.entry - self.stop)
        return abs(self.target - self.entry) / risk if risk else 0.0


def generate_signals(df: pd.DataFrame,
                     min_rr: float = MIN_RR,
                     min_confluence: int = MIN_CONFLUENCE,
                     recent: int = SIGNAL_FRESHNESS_BARS) -> list:
    """df needs columns open/high/low/close and a DatetimeIndex."""
    structure = analyze_structure(df)
    pools = find_liquidity_pools(df)
    sweeps = find_liquidity_sweeps(df, pools)
    gaps = find_fair_value_gaps(df)
    blocks = find_order_blocks(df)

    signals: list[Signal] = []
    last_fired = {"long": -10**9, "short": -10**9}

    for i in range(len(df)):
        zone = active_kill_zone(df.index[i])
        if zone is None:
            continue

        bar_low, bar_high = float(df["low"].iloc[i]), float(df["high"].iloc[i])
        close = float(df["close"].iloc[i])

        for direction in ("long", "short"):
            if i - last_fired[direction] < SIGNAL_COOLDOWN_BARS:
                continue
            bullish = direction == "long"
            want = "bullish" if bullish else "bearish"

            # 2. bar taps an aligned, still-valid OB or FVG (required)
            zone_hit = None
            for ob in blocks:
                if (ob.direction == want and ob.index < i
                        and (ob.invalidated_at is None or ob.invalidated_at > i)
                        and bar_low <= ob.top and bar_high >= ob.bottom):
                    zone_hit = ("order block", ob.top, ob.bottom)
                    break
            if zone_hit is None:
                for gap in gaps:
                    if (gap.direction == want and gap.index < i
                            and (gap.filled_at is None or gap.filled_at > i)
                            and bar_low <= gap.top and bar_high >= gap.bottom):
                        zone_hit = ("fair value gap", gap.top, gap.bottom)
                        break
            if zone_hit is None:
                continue

            reasons = []
            confluence = 0

            # 3. a recent sweep of the pool opposite our direction
            sweep = next((p for p in sweeps if p.swept_at is not None
                          and 0 <= i - p.swept_at <= recent
                          and p.side == ("sell_side" if bullish else "buy_side")),
                         None)
            if sweep is not None:
                confluence += 1
                reasons.append(
                    f"{'sell-side' if bullish else 'buy-side'} liquidity swept "
                    f"at {sweep.price:.0f} (bar {sweep.swept_at})")

            # 4. a recent structure event our way
            event = next((e for e in reversed(structure.events)
                          if e.index <= i and i - e.index <= recent
                          and e.direction == want),
                         None)
            if event is not None:
                confluence += 1
                reasons.append(
                    f"{event.kind} {event.direction} through {event.price:.0f}")

            if confluence < min_confluence:
                continue

            zone_name, zone_top, zone_bottom = zone_hit
            reasons.append(f"price tapped {want} {zone_name} "
                           f"{zone_bottom:.0f}-{zone_top:.0f}")

            entry = close
            stop = zone_bottom - 1.0 if bullish else zone_top + 1.0
            risk = abs(entry - stop)
            if risk == 0:
                continue

            # target: nearest unswept opposing pool, else fixed MIN_RR
            if bullish:
                pool_targets = [p.price for p in pools
                                if p.side == "buy_side" and p.swept_at is None
                                and p.price >= entry + min_rr * risk]
                target = min(pool_targets) if pool_targets \
                    else entry + min_rr * risk
            else:
                pool_targets = [p.price for p in pools
                                if p.side == "sell_side" and p.swept_at is None
                                and p.price <= entry - min_rr * risk]
                target = max(pool_targets) if pool_targets \
                    else entry - min_rr * risk
            if pool_targets:
                reasons.append(f"targeting resting liquidity at {target:.0f}")
            else:
                reasons.append(f"no pool in reach - fixed {min_rr:.0f}R target "
                               f"at {target:.0f}")

            sig = Signal(index=i, time=df.index[i], direction=direction,
                         entry=entry, stop=stop, target=target,
                         kill_zone=zone, confluence=confluence,
                         reasons=reasons)
            if sig.rr >= min_rr:
                signals.append(sig)
                last_fired[direction] = i

    return signals
