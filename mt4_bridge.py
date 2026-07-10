"""Python side of the MT4 file bridge (pairs with mt4/US30Sentinel.mq4).

The EA exports broker bars and account state into the terminal's
MQL4/Files folder; this module reads them and writes order commands back.
Bar timestamps arrive in broker server time; the EA also exports its
current server and GMT clocks, so bars are shifted to real UTC using the
live offset (close enough within a few days of history for kill zones).
"""
import math
import os
import time

import pandas as pd

from config import MT4_FILES_DIR, MT4_MAX_LOTS, RISK_PER_TRADE

BARS_FILE = "ict_bars.csv"
STATUS_FILE = "ict_status.csv"
COMMAND_FILE = "ict_commands.csv"
RESULT_FILE = "ict_results.csv"


class MT4Bridge:
    def __init__(self, files_dir: str = MT4_FILES_DIR):
        if not files_dir or not os.path.isdir(files_dir):
            raise RuntimeError(
                "MT4_FILES_DIR is not set or does not exist. In MT4 use "
                "File -> Open Data Folder, then point config.MT4_FILES_DIR "
                "at the MQL4\\Files folder inside it.")
        self.dir = files_dir

    def _path(self, name: str) -> str:
        return os.path.join(self.dir, name)

    # --- reading what the EA exports --------------------------------------
    def read_bars(self) -> tuple[pd.DataFrame, dict]:
        with open(self._path(BARS_FILE)) as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
        if not lines or not lines[0].startswith("meta,"):
            raise RuntimeError("bars file has no meta header yet")
        m = lines[0].split(",")
        server_now, gmt_now = int(m[3]), int(m[4])
        meta = {
            "symbol": m[1],
            "period": int(m[2]),
            "utc_offset": server_now - gmt_now,   # seconds server is ahead of UTC
            "point_value_per_lot": float(m[5]),   # $ per point per 1.0 lot
            "min_lot": float(m[6]),
            "max_lot": float(m[7]),
            "lot_step": float(m[8]),
        }
        rows = [ln.split(",") for ln in lines[1:]]
        if not rows:
            raise RuntimeError("bars file has no bars yet")
        df = pd.DataFrame(rows, columns=["time", "open", "high", "low",
                                         "close"]).astype(float)
        utc_seconds = df["time"].astype(int) - meta["utc_offset"]
        df.index = pd.to_datetime(utc_seconds, unit="s", utc=True)
        df = df.drop(columns=["time"]).sort_index()
        return df, meta

    def read_status(self) -> dict:
        status: dict = {}
        with open(self._path(STATUS_FILE)) as fh:
            for ln in fh:
                if "," not in ln:
                    continue
                key, value = ln.strip().split(",", 1)
                try:
                    status[key] = float(value) if "." in value \
                        else int(value)
                except ValueError:
                    status[key] = value
        return status

    def read_results(self, after_id: int = 0) -> list[tuple]:
        path = self._path(RESULT_FILE)
        if not os.path.exists(path):
            return []
        out = []
        with open(path) as fh:
            for ln in fh:
                parts = ln.strip().split(",", 3)
                if len(parts) == 4 and parts[0].isdigit() \
                        and int(parts[0]) > after_id:
                    out.append((int(parts[0]), parts[2], parts[3]))
        return out

    # --- writing commands ---------------------------------------------------
    def _next_id(self) -> int:
        last = 0
        path = self._path(COMMAND_FILE)
        if os.path.exists(path):
            with open(path) as fh:
                for ln in fh:
                    head = ln.split(",", 1)[0]
                    if head.isdigit():
                        last = max(last, int(head))
        return max(last + 1, int(time.time()))

    def _send(self, line: str) -> int:
        cmd_id = self._next_id()
        with open(self._path(COMMAND_FILE), "a") as fh:
            fh.write(f"{cmd_id},{int(time.time())},{line}\n")
        return cmd_id

    def send_open(self, direction: str, lots: float,
                  sl: float, tp: float) -> int:
        return self._send(f"open,{direction},{lots:.2f},{sl:.1f},{tp:.1f}")

    def send_close(self) -> int:
        return self._send("close")

    # --- position sizing ------------------------------------------------------
    def lot_size(self, balance: float, risk_points: float,
                 meta: dict, risk_fraction: float = RISK_PER_TRADE) -> float:
        """Lots such that a stop-out loses `risk_fraction` of balance.
        Returns 0.0 when even the broker minimum lot would risk more."""
        if risk_points <= 0 or meta["point_value_per_lot"] <= 0:
            return 0.0
        raw = (balance * risk_fraction) / (risk_points
                                           * meta["point_value_per_lot"])
        step = meta["lot_step"]
        lots = math.floor(raw / step) * step
        lots = min(lots, meta["max_lot"], MT4_MAX_LOTS)
        if lots < meta["min_lot"]:
            return 0.0
        return round(lots, 2)
