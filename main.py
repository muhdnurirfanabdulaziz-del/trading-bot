"""US30 ICT analysis runner.

Usage:
    python main.py                 # run on built-in synthetic US30 data
    python main.py path/to/us30.csv   # run on your own OHLC export
"""
import sys

import pandas as pd

from config import TICKER
from data import load_csv, sample_us30
from ict import (
    analyze_structure,
    find_fair_value_gaps,
    find_liquidity_pools,
    find_liquidity_sweeps,
    find_order_blocks,
    generate_signals,
)
from ict.killzones import kill_zone_mask


def moving_average_strategy(prices: list[float]) -> list[str]:
    """Legacy MA crossover, kept for reference/tests."""
    from config import LONG_WINDOW, SHORT_WINDOW
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


def run(df: pd.DataFrame) -> None:
    print(f"=== {TICKER} ICT analysis: {len(df)} bars "
          f"({df.index[0]} -> {df.index[-1]}) ===\n")

    structure = analyze_structure(df)
    print(f"Trend now: {structure.trend}")
    print("Structure events (last 5):")
    for e in structure.events[-5:]:
        print(f"  bar {e.index:>4}  {e.kind:<5} {e.direction:<8} "
              f"through {e.price:.0f}")

    pools = find_liquidity_pools(df)
    sweeps = find_liquidity_sweeps(df, pools)
    bsl = [p for p in pools if p.side == "buy_side" and p.swept_at is None]
    ssl = [p for p in pools if p.side == "sell_side" and p.swept_at is None]
    print(f"\nLiquidity: {len(bsl)} buy-side pools resting above, "
          f"{len(ssl)} sell-side below, {len(sweeps)} swept")
    for p in sweeps[-3:]:
        print(f"  swept {p.side.replace('_', '-')} {p.price:.0f} "
              f"(strength {p.strength}) at bar {p.swept_at}")

    gaps = find_fair_value_gaps(df)
    open_gaps = [g for g in gaps if g.filled_at is None]
    print(f"\nFair value gaps: {len(gaps)} found, {len(open_gaps)} still open")
    for g in open_gaps[-3:]:
        print(f"  {g.direction:<8} {g.bottom:.0f}-{g.top:.0f} "
              f"(CE {g.midpoint:.0f})")

    blocks = find_order_blocks(df)
    live_obs = [b for b in blocks if b.invalidated_at is None]
    print(f"\nOrder blocks: {len(blocks)} found, {len(live_obs)} still valid")
    for b in live_obs[-3:]:
        state = "mitigated" if b.mitigated_at is not None else "unmitigated"
        print(f"  {b.direction:<8} {b.bottom:.0f}-{b.top:.0f} ({state})")

    kz_bars = int(kill_zone_mask(df.index).sum())
    print(f"\nKill zones: {kz_bars} of {len(df)} bars inside "
          f"London Open / New York AM")

    signals = generate_signals(df)
    print(f"\n=== Signals: {len(signals)} ===")
    for s in signals:
        print(f"\n[{s.time}] {s.direction.upper()} @ {s.entry:.0f} "
              f"({s.kill_zone})")
        print(f"  stop {s.stop:.0f}  target {s.target:.0f}  RR {s.rr:.1f}")
        for r in s.reasons:
            print(f"  - {r}")
    if not signals:
        print("No A+ setups: confluence (sweep + structure + zone + kill "
              "zone + RR) not met.")


if __name__ == "__main__":
    df = load_csv(sys.argv[1]) if len(sys.argv) > 1 else sample_us30()
    run(df)
