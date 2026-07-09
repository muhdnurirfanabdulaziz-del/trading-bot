"""Paper-trade execution: enters ICT signals, manages them to stop/target.

State survives restarts via a JSON file; every closed trade is appended to
a CSV log. Position size is risk-based: RISK_PER_TRADE of the account is
lost if the stop is hit.
"""
import csv
import json
import os
from dataclasses import asdict, dataclass

import pandas as pd

from config import (
    ACCOUNT_BALANCE,
    PAPER_STATE_FILE,
    POINT_VALUE,
    RISK_PER_TRADE,
    TICKER,
    TRADE_LOG_FILE,
)


@dataclass
class Position:
    opened_at: str
    direction: str        # "long" | "short"
    entry: float
    stop: float
    target: float
    size: float           # units; P&L = size * points * POINT_VALUE
    reasons: list


class PaperTrader:
    def __init__(self,
                 state_file: str = PAPER_STATE_FILE,
                 log_file: str = TRADE_LOG_FILE):
        self.state_file = state_file
        self.log_file = log_file
        self.balance = ACCOUNT_BALANCE
        self.position: Position | None = None
        self.closed_trades = 0
        self.wins = 0
        self._load()

    # --- persistence -----------------------------------------------------
    def _load(self) -> None:
        if not os.path.exists(self.state_file):
            return
        with open(self.state_file) as fh:
            state = json.load(fh)
        self.balance = state["balance"]
        self.closed_trades = state.get("closed_trades", 0)
        self.wins = state.get("wins", 0)
        if state.get("position"):
            self.position = Position(**state["position"])

    def _save(self) -> None:
        state = {
            "balance": self.balance,
            "closed_trades": self.closed_trades,
            "wins": self.wins,
            "position": asdict(self.position) if self.position else None,
        }
        with open(self.state_file, "w") as fh:
            json.dump(state, fh, indent=2)

    def _log(self, row: dict) -> None:
        new_file = not os.path.exists(self.log_file)
        with open(self.log_file, "a", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(row))
            if new_file:
                writer.writeheader()
            writer.writerow(row)

    # --- trading ---------------------------------------------------------
    @property
    def in_position(self) -> bool:
        return self.position is not None

    def enter(self, signal) -> Position:
        """Open a position from an ICT signal (one at a time)."""
        if self.position is not None:
            raise RuntimeError("already in a position")
        risk_points = abs(signal.entry - signal.stop)
        size = (self.balance * RISK_PER_TRADE) / (risk_points * POINT_VALUE)
        self.position = Position(
            opened_at=str(signal.time),
            direction=signal.direction,
            entry=float(signal.entry),
            stop=float(signal.stop),
            target=float(signal.target),
            size=round(size, 4),
            reasons=list(signal.reasons),
        )
        self._save()
        print(f">>> ENTERED {signal.direction.upper()} {TICKER} "
              f"@ {signal.entry:.0f} | size {size:.2f} "
              f"| stop {signal.stop:.0f} | target {signal.target:.0f}")
        return self.position

    def update(self, df: pd.DataFrame) -> None:
        """Walk bars after entry; close on stop/target touch.
        If a bar spans both, assume the stop was hit first (conservative)."""
        if self.position is None:
            return
        pos = self.position
        opened = pd.Timestamp(pos.opened_at)
        bars = df[df.index > opened]
        for ts, bar in bars.iterrows():
            hi, lo = float(bar["high"]), float(bar["low"])
            if pos.direction == "long":
                if lo <= pos.stop:
                    self._close(ts, pos.stop, "stop")
                    return
                if hi >= pos.target:
                    self._close(ts, pos.target, "target")
                    return
            else:
                if hi >= pos.stop:
                    self._close(ts, pos.stop, "stop")
                    return
                if lo <= pos.target:
                    self._close(ts, pos.target, "target")
                    return

    def _close(self, ts, price: float, hit: str) -> None:
        pos = self.position
        points = (price - pos.entry) if pos.direction == "long" \
            else (pos.entry - price)
        pnl = points * pos.size * POINT_VALUE
        self.balance += pnl
        self.closed_trades += 1
        if pnl > 0:
            self.wins += 1
        self.position = None
        self._save()
        self._log({
            "opened_at": pos.opened_at, "closed_at": str(ts),
            "direction": pos.direction, "entry": pos.entry,
            "exit": price, "hit": hit, "size": pos.size,
            "pnl": round(pnl, 2), "balance": round(self.balance, 2),
        })
        word = "TARGET HIT" if hit == "target" else "STOPPED OUT"
        print(f">>> {word}: {pos.direction.upper()} closed @ {price:.0f} "
              f"| P&L {pnl:+.2f} | balance {self.balance:.2f}")

    def status(self) -> str:
        win_rate = (self.wins / self.closed_trades * 100
                    if self.closed_trades else 0.0)
        line = (f"Paper account: {self.balance:.2f} "
                f"| trades {self.closed_trades} | win rate {win_rate:.0f}%")
        if self.position:
            p = self.position
            line += (f"\nOpen position: {p.direction.upper()} "
                     f"@ {p.entry:.0f} (stop {p.stop:.0f}, "
                     f"target {p.target:.0f}, size {p.size:.2f})")
        else:
            line += "\nOpen position: none (flat)"
        return line
