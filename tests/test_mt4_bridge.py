import pandas as pd
import pytest

import mt4_bridge
from mt4_bridge import MT4Bridge

# server clock UTC+3 (typical EET broker in summer)
SERVER_NOW = 1_783_000_000 + 3 * 3600
GMT_NOW = 1_783_000_000
META = (f"meta,US30,5,{SERVER_NOW},{GMT_NOW},1.00000,0.10,50.00,0.10")


def write_bars(tmp_path, n=5):
    lines = [META]
    for i in range(n):
        t = SERVER_NOW - (n - i) * 300
        px = 44_000 + i * 10
        lines.append(f"{t},{px - 3:.2f},{px + 6:.2f},{px - 8:.2f},{px:.2f}")
    (tmp_path / "ict_bars.csv").write_text("\n".join(lines) + "\n")


def write_status(tmp_path, position=0, extra=""):
    body = (f"balance,10000.00\nequity,10000.00\ncurrency,USD\n"
            f"trading_enabled,0\nlast_command_id,0\ntime_gmt,{GMT_NOW}\n"
            f"position,{position}\n{extra}")
    (tmp_path / "ict_status.csv").write_text(body)


def bridge(tmp_path) -> MT4Bridge:
    return MT4Bridge(files_dir=str(tmp_path))


class TestBridge:
    def test_rejects_missing_dir(self):
        with pytest.raises(RuntimeError, match="MT4_FILES_DIR"):
            MT4Bridge(files_dir="/nonexistent/mql4/files")

    def test_bars_shifted_to_utc(self, tmp_path):
        write_bars(tmp_path)
        df, meta = bridge(tmp_path).read_bars()
        assert meta["symbol"] == "US30" and meta["period"] == 5
        assert meta["utc_offset"] == 3 * 3600
        assert str(df.index.tz) == "UTC"
        # newest bar is 300s (one M5 bar) before "now" in real UTC
        assert int(df.index[-1].timestamp()) == GMT_NOW - 300
        assert list(df.columns) == ["open", "high", "low", "close"]

    def test_status_parses_types(self, tmp_path):
        write_status(tmp_path, position=1,
                     extra="ticket,123\ndirection,long\nlots,0.50\n"
                           "entry,44100.00\nsl,44050.00\ntp,44300.00\n"
                           "profit,12.50\n")
        st = bridge(tmp_path).read_status()
        assert st["balance"] == 10_000.0
        assert st["position"] == 1
        assert st["direction"] == "long"
        assert st["sl"] == 44_050.0

    def test_lot_size_risks_the_configured_fraction(self, tmp_path):
        write_bars(tmp_path)
        b = bridge(tmp_path)
        _, meta = b.read_bars()
        # 1% of 10k = $100 over 40 points at $1/pt/lot -> 2.5 lots
        assert b.lot_size(10_000, 40, meta, risk_fraction=0.01) == 2.5

    def test_lot_size_respects_step_min_and_cap(self, tmp_path):
        write_bars(tmp_path)
        b = bridge(tmp_path)
        _, meta = b.read_bars()
        # rounds DOWN to the 0.10 step
        assert b.lot_size(10_000, 130, meta, risk_fraction=0.01) == 0.7
        # below broker minimum -> refuse to trade rather than over-risk
        assert b.lot_size(200, 40, meta, risk_fraction=0.01) == 0.0
        # huge account -> clamped by MT4_MAX_LOTS
        assert b.lot_size(10_000_000, 40, meta,
                          risk_fraction=0.01) == mt4_bridge.MT4_MAX_LOTS

    def test_command_ids_increase(self, tmp_path):
        b = bridge(tmp_path)
        first = b.send_open("long", 0.5, 44_050.0, 44_300.0)
        second = b.send_close()
        assert second > first
        lines = (tmp_path / "ict_commands.csv").read_text().strip().splitlines()
        assert lines[0].endswith("open,long,0.50,44050.0,44300.0")
        assert lines[1].endswith("close")

    def test_results_filtered_by_id(self, tmp_path):
        (tmp_path / "ict_results.csv").write_text(
            "5,1783000000,dry_run,would open long\n"
            "9,1783000100,opened,ticket 123 long 0.50 lots @ 44100.0\n")
        res = bridge(tmp_path).read_results(after_id=5)
        assert res == [(9, "opened", "ticket 123 long 0.50 lots @ 44100.0")]
