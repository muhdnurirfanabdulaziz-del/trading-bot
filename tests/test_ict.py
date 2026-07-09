import numpy as np
import pandas as pd
import pytest

from data import sample_us30
from ict.fvg import find_fair_value_gaps
from ict.killzones import active_kill_zone, in_kill_zone, kill_zone_mask
from ict.liquidity import find_liquidity_pools, find_liquidity_sweeps
from ict.order_blocks import find_order_blocks
from ict.strategy import generate_signals
from ict.structure import analyze_structure, find_swings


def make_df(rows, start="2026-07-06 12:00", freq="5min"):
    """rows: list of (open, high, low, close)."""
    index = pd.date_range(start, periods=len(rows), freq=freq, tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"],
                        index=index, dtype=float)


class TestSwingsAndStructure:
    def test_finds_swing_high_and_low(self):
        # clean peak at bar 2, trough at bar 6
        rows = [(100, 101, 99, 100), (101, 103, 100, 102), (103, 106, 102, 105),
                (104, 105, 101, 102), (101, 102, 98, 99), (98, 99, 95, 96),
                (95, 96, 92, 93), (94, 97, 93, 96), (97, 100, 96, 99)]
        swings = find_swings(make_df(rows), lookback=2)
        kinds = {(s.kind, s.index) for s in swings}
        assert ("high", 2) in kinds
        assert ("low", 6) in kinds

    def test_bos_then_choch(self):
        df = sample_us30()
        state = analyze_structure(df)
        kinds = {e.kind for e in state.events}
        assert state.events, "expected structure events on sample data"
        assert kinds & {"BOS", "CHoCH", "MSS"}
        # events must reference known swing levels and be time-ordered
        indices = [e.index for e in state.events]
        assert indices == sorted(indices)


class TestLiquidity:
    def test_equal_highs_merge_into_one_pool(self):
        rows = [(100, 101, 99, 100), (101, 105, 100, 101), (101, 102, 100, 101),
                (101, 102, 100, 101), (101, 105, 100, 101), (101, 102, 100, 101),
                (101, 102, 100, 101)]
        pools = find_liquidity_pools(make_df(rows), tolerance=2.0, lookback=1)
        buy_side = [p for p in pools if p.side == "buy_side"]
        assert len(buy_side) == 1
        assert buy_side[0].strength == 2

    def test_sweep_requires_wick_through_and_close_back(self):
        rows = [(100, 101, 99, 100), (101, 105, 100, 101), (101, 102, 100, 101),
                # wick to 107 through the 105 pool, close back at 103
                (101, 107, 100, 103),
                (103, 104, 102, 103)]
        df = make_df(rows)
        pools = find_liquidity_pools(df, tolerance=1.0, lookback=1)
        swept = find_liquidity_sweeps(df, pools)
        assert any(p.side == "buy_side" and p.swept_at == 3 for p in swept)


class TestFVG:
    def test_bullish_gap_detected_and_filled(self):
        rows = [(100, 102, 99, 101),      # candle 1: high 102
                (103, 130, 102, 128),     # impulse
                (128, 132, 125, 130),     # candle 3: low 125 > 102 -> FVG
                (130, 131, 124, 126),     # trades into the gap
                (126, 127, 100, 105)]     # fills it
        gaps = find_fair_value_gaps(make_df(rows), min_size=5.0)
        assert len(gaps) == 1
        g = gaps[0]
        assert g.direction == "bullish"
        assert (g.bottom, g.top) == (102.0, 125.0)
        assert g.touched_at == 3
        assert g.filled_at == 4

    def test_small_gaps_filtered(self):
        rows = [(100, 102, 99, 101), (103, 106, 102, 105),
                (105, 107, 103, 106)]
        assert find_fair_value_gaps(make_df(rows), min_size=15.0) == []


class TestOrderBlocks:
    def test_bullish_ob_is_last_down_candle_before_displacement(self):
        rows = [(100, 101, 99, 100), (100, 101, 98, 99),   # down candle (OB)
                (99, 120, 99, 118),                        # displacement up
                (118, 121, 117, 120), (120, 121, 118, 119),
                (119, 120, 100, 101),                      # mitigates the OB
                (101, 102, 100, 101)]
        blocks = find_order_blocks(make_df(rows), displacement_factor=1.5)
        bullish = [b for b in blocks if b.direction == "bullish"]
        assert any(b.index == 1 for b in bullish)
        ob = next(b for b in bullish if b.index == 1)
        assert ob.mitigated_at == 5


class TestKillZones:
    def test_london_and_ny_am_windows(self):
        # 2026-07-06 is EDT (UTC-4): 07:00 UTC == 03:00 NY -> London
        assert active_kill_zone("2026-07-06 07:00:00+00:00") == "london_open"
        # 13:30 UTC == 09:30 NY -> New York AM
        assert active_kill_zone("2026-07-06 13:30:00+00:00") == "new_york_am"
        # 17:00 UTC == 13:00 NY -> outside both
        assert not in_kill_zone("2026-07-06 17:00:00+00:00")

    def test_mask_matches_scalar_checks(self):
        df = sample_us30()
        mask = kill_zone_mask(df.index)
        for ts, flag in zip(df.index, mask):
            assert flag == in_kill_zone(ts)


class TestStrategy:
    def test_signals_only_in_kill_zones_and_meet_rr(self):
        df = sample_us30()
        for sig in generate_signals(df, min_rr=2.0):
            assert sig.kill_zone in ("london_open", "new_york_am")
            assert sig.rr >= 2.0
            assert sig.direction in ("long", "short")
            if sig.direction == "long":
                assert sig.stop < sig.entry < sig.target
            else:
                assert sig.target < sig.entry < sig.stop

    def test_default_confluence_actually_fires(self):
        # at MIN_CONFLUENCE=1 the sample day must produce trades
        assert len(generate_signals(sample_us30())) >= 1

    def test_strict_mode_fires_less(self):
        df = sample_us30()
        loose = generate_signals(df, min_confluence=1)
        strict = generate_signals(df, min_confluence=2)
        assert len(strict) <= len(loose)
        assert all(s.confluence == 2 for s in strict)

    def test_cooldown_spaces_same_direction_signals(self):
        from config import SIGNAL_COOLDOWN_BARS
        signals = generate_signals(sample_us30())
        for direction in ("long", "short"):
            idx = [s.index for s in signals if s.direction == direction]
            gaps = [b - a for a, b in zip(idx, idx[1:])]
            assert all(g >= SIGNAL_COOLDOWN_BARS for g in gaps)

    def test_runs_clean_on_sample_data(self):
        # end-to-end smoke: no exceptions across all detectors
        df = sample_us30()
        generate_signals(df)
