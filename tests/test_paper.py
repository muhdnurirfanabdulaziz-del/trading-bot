import pandas as pd

from ict.paper import PaperTrader
from ict.strategy import Signal


def make_signal(direction="long", entry=44_000.0, stop=43_980.0,
                target=44_060.0, time="2026-07-06 13:30:00+00:00"):
    return Signal(index=50, time=pd.Timestamp(time), direction=direction,
                  entry=entry, stop=stop, target=target,
                  kill_zone="new_york_am", confluence=2, reasons=["test"])


def make_bars(rows, start="2026-07-06 13:35", freq="5min"):
    index = pd.date_range(start, periods=len(rows), freq=freq, tz="UTC")
    return pd.DataFrame(rows, columns=["open", "high", "low", "close"],
                        index=index, dtype=float)


def trader(tmp_path) -> PaperTrader:
    return PaperTrader(state_file=str(tmp_path / "state.json"),
                       log_file=str(tmp_path / "trades.csv"))


class TestPaperTrader:
    def test_position_size_risks_one_percent(self, tmp_path):
        t = trader(tmp_path)
        t.enter(make_signal())          # 20 points risk on 10k @ 1%
        assert t.position.size == 5.0   # 100 / 20

    def test_target_hit_pays_at_rr(self, tmp_path):
        t = trader(tmp_path)
        t.enter(make_signal())          # long 44000, stop -20, target +60
        bars = make_bars([(44_000, 44_070, 43_995, 44_060)])
        t.update(bars)
        assert t.position is None
        assert t.balance == 10_000 + 60 * 5.0
        assert t.wins == 1

    def test_stop_hit_loses_risk(self, tmp_path):
        t = trader(tmp_path)
        t.enter(make_signal())
        bars = make_bars([(44_000, 44_010, 43_975, 43_990)])
        t.update(bars)
        assert t.position is None
        assert t.balance == 10_000 - 100.0

    def test_bar_spanning_both_counts_as_stop(self, tmp_path):
        t = trader(tmp_path)
        t.enter(make_signal())
        bars = make_bars([(44_000, 44_070, 43_975, 44_050)])
        t.update(bars)
        assert t.balance == 10_000 - 100.0   # conservative fill

    def test_short_side(self, tmp_path):
        t = trader(tmp_path)
        t.enter(make_signal(direction="short", entry=44_000, stop=44_020,
                            target=43_940))
        bars = make_bars([(44_000, 44_005, 43_930, 43_950)])
        t.update(bars)
        assert t.balance == 10_000 + 60 * 5.0

    def test_state_survives_restart(self, tmp_path):
        t1 = trader(tmp_path)
        t1.enter(make_signal())
        t2 = trader(tmp_path)                # fresh instance, same files
        assert t2.in_position
        assert t2.position.entry == 44_000.0
        bars = make_bars([(44_000, 44_070, 43_995, 44_060)])
        t2.update(bars)
        t3 = trader(tmp_path)
        assert t3.balance == 10_000 + 300.0
        assert t3.closed_trades == 1

    def test_only_bars_after_entry_count(self, tmp_path):
        t = trader(tmp_path)
        t.enter(make_signal())
        # bar BEFORE the entry time would have hit the stop - must be ignored
        old = make_bars([(44_000, 44_010, 43_900, 43_990)],
                        start="2026-07-06 13:00")
        t.update(old)
        assert t.in_position

    def test_trade_log_written(self, tmp_path):
        t = trader(tmp_path)
        t.enter(make_signal())
        t.update(make_bars([(44_000, 44_070, 43_995, 44_060)]))
        log = (tmp_path / "trades.csv").read_text()
        assert "target" in log and "300.0" in log
