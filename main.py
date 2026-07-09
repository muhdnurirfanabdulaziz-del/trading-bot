"""US30 ICT trading bot.

Usage:
    python main.py                    # one-shot: live US30 data -> ICT analysis
    python main.py --live             # keep polling every REFRESH_SECONDS
    python main.py --demo             # run on built-in synthetic US30 data
    python main.py path/to/us30.csv   # run on your own OHLC export
"""
import sys
import time

import pandas as pd

from config import (
    LONG_WINDOW,
    MACD_FAST,
    MACD_SIGNAL,
    MACD_SLOW,
    REFRESH_SECONDS,
    SHORT_WINDOW,
    TICKER,
    VOLUME_WINDOW,
    YF_SYMBOL,
)
from data import fetch_ohlc, load_csv, sample_us30
from ict import (
    analyze_structure,
    find_fair_value_gaps,
    find_liquidity_pools,
    find_liquidity_sweeps,
    find_order_blocks,
    generate_signals,
)
from ict.killzones import active_kill_zone, kill_zone_mask


def compute_macd(prices: pd.Series) -> tuple[pd.Series, pd.Series]:
    fast_ema = prices.ewm(span=MACD_FAST, adjust=False).mean()
    slow_ema = prices.ewm(span=MACD_SLOW, adjust=False).mean()
    macd_line = fast_ema - slow_ema
    signal_line = macd_line.ewm(span=MACD_SIGNAL, adjust=False).mean()
    return macd_line, signal_line


def moving_average_strategy(prices: list[float],
                            volumes: list[float] | None = None) -> list[str]:
    """Legacy filter stack: SMA crossover + volume + MACD must all agree.

    Without volume data the volume condition is skipped.
    """
    price_series = pd.Series(prices)
    short_ma = price_series.rolling(SHORT_WINDOW).mean()
    long_ma = price_series.rolling(LONG_WINDOW).mean()

    if volumes is not None:
        volume_series = pd.Series(volumes)
        volume_ma = volume_series.rolling(VOLUME_WINDOW).mean()

    macd_line, signal_line = compute_macd(price_series)

    signals = []
    for i in range(len(prices)):
        above_volume = (volumes is None
                        or bool(volume_series[i] > volume_ma[i]))
        macd_bullish = macd_line[i] > signal_line[i]
        if short_ma[i] > long_ma[i] and above_volume and macd_bullish:
            signals.append("buy")
        elif short_ma[i] < long_ma[i] and above_volume and not macd_bullish:
            signals.append("sell")
        else:
            signals.append("hold")
    return signals


def run(df: pd.DataFrame) -> list:
    """Full ICT report over df; returns the confluence signals."""
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
    print(f"\n=== ICT signals: {len(signals)} ===")
    for s in signals:
        print(f"\n[{s.time}] {s.direction.upper()} @ {s.entry:.0f} "
              f"({s.kill_zone})")
        print(f"  stop {s.stop:.0f}  target {s.target:.0f}  RR {s.rr:.1f}")
        for r in s.reasons:
            print(f"  - {r}")
    if not signals:
        print("No A+ setups: confluence (sweep + structure + zone + kill "
              "zone + RR) not met.")
    return signals


def print_legacy_signal(df: pd.DataFrame) -> None:
    prices = df["close"].tolist()
    volumes = df["volume"].tolist() if "volume" in df.columns else None
    signal = moving_average_strategy(prices, volumes)[-1]
    print(f"\nLegacy MA/MACD signal: {signal.upper()} "
          f"@ {prices[-1]:.0f}")


def live_once() -> list:
    print(f"Fetching live {TICKER} candles ({YF_SYMBOL})...")
    df = fetch_ohlc()
    signals = run(df)
    print_legacy_signal(df)

    now = df.index[-1]
    zone = active_kill_zone(now)
    print(f"\nLast bar {now} -> kill zone: {zone or 'none (stand aside)'}")
    return signals


def live_loop() -> None:
    """Poll the feed each REFRESH_SECONDS and announce only new ICT signals."""
    seen: set = set()
    print(f"Live mode: refreshing every {REFRESH_SECONDS}s. Ctrl-C to stop.\n")
    while True:
        try:
            signals = live_once()
            for s in signals:
                key = (s.time, s.direction)
                if key not in seen:
                    seen.add(key)
                    print(f"\n*** NEW SETUP: {s.direction.upper()} "
                          f"{TICKER} @ {s.entry:.0f} | stop {s.stop:.0f} "
                          f"| target {s.target:.0f} | RR {s.rr:.1f} ***")
        except Exception as exc:          # keep the loop alive on feed hiccups
            print(f"[warn] {exc}")
        print("-" * 60)
        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg == "--demo":
        df = sample_us30()
        run(df)
    elif arg == "--live":
        live_loop()
    elif arg:
        df = load_csv(arg)
        run(df)
        print_legacy_signal(df)
    else:
        live_once()
