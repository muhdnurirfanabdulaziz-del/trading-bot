"""Kill zones - the high-volatility windows where institutional algos are active.

Defaults (New York local time, so EST/EDT is handled automatically):
- London Open : 02:00 - 05:00
- New York AM : 08:30 - 11:00
"""
from datetime import datetime, time
from zoneinfo import ZoneInfo

import pandas as pd

from config import KILL_ZONES, TIMEZONE

_NY = ZoneInfo(TIMEZONE)


def _parse(t: str) -> time:
    hour, minute = map(int, t.split(":"))
    return time(hour, minute)


def _to_ny(ts) -> datetime:
    """Interpret a timestamp in New York time. Naive stamps are assumed UTC
    (the norm for broker/exchange feeds)."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert(_NY)


def active_kill_zone(ts) -> str | None:
    """Name of the kill zone `ts` falls in, or None."""
    local = _to_ny(ts).time()
    for name, (start, end) in KILL_ZONES.items():
        if _parse(start) <= local < _parse(end):
            return name
    return None


def in_kill_zone(ts) -> bool:
    return active_kill_zone(ts) is not None


def kill_zone_mask(index: pd.DatetimeIndex) -> pd.Series:
    """Boolean mask over a DatetimeIndex - True where the bar opens inside
    a kill zone. Vectorised for backtests."""
    idx = pd.DatetimeIndex(index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    local = idx.tz_convert(_NY)
    mask = pd.Series(False, index=index)
    minutes = local.hour * 60 + local.minute
    for start, end in KILL_ZONES.values():
        s, e = _parse(start), _parse(end)
        mask |= pd.Series((minutes >= s.hour * 60 + s.minute)
                          & (minutes < e.hour * 60 + e.minute),
                          index=index)
    return mask
