"""US30 ICT trading bot.

Usage:
    python main.py                    # one-shot: live US30 data -> ICT analysis
    python main.py --live             # paper-trade on yfinance data
    python main.py --mt4              # trade through MetaTrader 4 (see mt4/)
    python main.py --demo             # run on built-in synthetic US30 data
    python main.py path/to/us30.csv   # run on your own OHLC export
"""
import sys
import time

import pandas as pd

from config import (
    KILL_ZONES_ONLY,
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
from ict.paper import PaperTrader

# a signal is tradeable if it fired on one of the last N closed bars
FRESH_BARS = 2


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


def live_once(trader: PaperTrader | None = None) -> list:
    print(f"Fetching live {TICKER} candles ({YF_SYMBOL})...")
    df = fetch_ohlc()
    signals = run(df)
    print_legacy_signal(df)

    now = df.index[-1]
    zone = active_kill_zone(now)
    if zone is None:
        where = ("off hours - trading with full confluence required"
                 if not KILL_ZONES_ONLY else "none (standing aside)")
    else:
        where = zone
    print(f"\nLast bar {now} -> kill zone: {where}")

    if trader is not None:
        # manage any open position against the newest bars first
        trader.update(df)
        # then, if flat, enter the freshest signal
        if not trader.in_position:
            fresh = [s for s in signals if s.index >= len(df) - FRESH_BARS]
            if fresh:
                trader.enter(fresh[-1])
        print(f"\n{trader.status()}")
    return signals


def live_loop() -> None:
    """Poll the feed each REFRESH_SECONDS; manage the paper account and
    enter new ICT setups as they appear."""
    trader = PaperTrader()
    print(f"Live mode: refreshing every {REFRESH_SECONDS}s. Ctrl-C to stop.")
    print(trader.status() + "\n")
    while True:
        try:
            live_once(trader)
        except Exception as exc:          # keep the loop alive on feed hiccups
            print(f"[warn] {exc}")
        print("-" * 60)
        time.sleep(REFRESH_SECONDS)


def mt4_loop() -> None:
    """Trade through MetaTrader 4 via the ICTBridge EA's file interface.

    Each poll: read broker bars + account state, run the ICT engine, and
    when flat send an open command (with stop and target attached) for a
    fresh signal. The EA enforces one position, a lot cap, and stays in
    dry-run mode until its InpEnableTrading input is switched on.
    """
    from config import MT4_POLL_SECONDS, RISK_PER_TRADE
    from mt4_bridge import MT4Bridge

    bridge = MT4Bridge()
    sent: set = set()
    last_result_id = 0
    print("MT4 bridge mode. The EA must be attached to your US30 M5 chart.")
    print("NOTE: orders only execute once the EA input InpEnableTrading is "
          "true - test on a DEMO account first.\n")

    while True:
        try:
            df, meta = bridge.read_bars()
            status = bridge.read_status()

            if meta["period"] != 5:
                print(f"[warn] EA chart is M{meta['period']}, expected M5 - "
                      f"attach ICTBridge to the 5-minute chart")

            for rid, outcome, detail in bridge.read_results(last_result_id):
                last_result_id = max(last_result_id, rid)
                print(f"EA result: {outcome} - {detail}")

            in_position = bool(status.get("position"))
            armed = bool(status.get("trading_enabled"))
            print(f"{df.index[-1]} | {meta['symbol']} M{meta['period']} "
                  f"| balance {status.get('balance', '?')} "
                  f"| {'POSITION OPEN' if in_position else 'flat'}"
                  f"{'' if armed else ' | EA DRY-RUN'}")
            if in_position:
                print(f"  {status.get('direction', '?').upper()} "
                      f"{status.get('lots')} lots @ {status.get('entry')} "
                      f"(sl {status.get('sl')}, tp {status.get('tp')}, "
                      f"P&L {status.get('profit')})")

            if not in_position:
                signals = generate_signals(df)
                fresh = [s for s in signals
                         if s.index >= len(df) - FRESH_BARS
                         and (s.time, s.direction) not in sent]
                if fresh:
                    s = fresh[-1]
                    lots = bridge.lot_size(float(status.get("balance", 0)),
                                           abs(s.entry - s.stop), meta)
                    if lots > 0:
                        cmd = bridge.send_open(s.direction, lots,
                                               s.stop, s.target)
                        sent.add((s.time, s.direction))
                        print(f">>> SENT {s.direction.upper()} {lots} lots "
                              f"| stop {s.stop:.0f} | target {s.target:.0f} "
                              f"| RR {s.rr:.1f} | cmd {cmd} ({s.kill_zone})")
                        for r in s.reasons:
                            print(f"    - {r}")
                    else:
                        print(f"[skip] signal found but risk sizing gave 0 "
                              f"lots (balance {status.get('balance')}, "
                              f"risk {RISK_PER_TRADE:.0%})")
        except FileNotFoundError as exc:
            print(f"waiting for EA files... ({exc})")
        except Exception as exc:      # keep the loop alive on partial writes
            print(f"[warn] {exc}")
        time.sleep(MT4_POLL_SECONDS)


if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg == "--demo":
        df = sample_us30()
        run(df)
    elif arg == "--live":
        live_loop()
    elif arg == "--mt4":
        mt4_loop()
    elif arg:
        df = load_csv(arg)
        run(df)
        print_legacy_signal(df)
    else:
        live_once(PaperTrader())
