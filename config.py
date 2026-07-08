# --- Instrument ---
TICKER = "US30"          # Dow Jones Industrial Average CFD/index
POINT_VALUE = 1.0        # $ per point per unit

# --- Legacy moving-average strategy ---
SHORT_WINDOW = 10
LONG_WINDOW = 50

# --- ICT / Smart Money Concepts ---
# Swing detection: a swing high/low needs this many lower/higher bars on each side.
SWING_LOOKBACK = 2

# Equal highs/lows are treated as one liquidity pool when within this many points.
# US30 moves in whole points; ~10 pts is a reasonable tolerance on M5-M15.
EQUAL_LEVEL_TOLERANCE = 10.0

# A fair value gap must be at least this many points wide to matter on US30.
MIN_FVG_SIZE = 15.0

# Displacement filter for order blocks: the move away from the OB must be at
# least this multiple of the average candle range to count as institutional.
DISPLACEMENT_FACTOR = 1.5

# --- Kill zones (New York local time, handles EST/EDT automatically) ---
TIMEZONE = "America/New_York"
KILL_ZONES = {
    "london_open": ("02:00", "05:00"),
    "new_york_am": ("08:30", "11:00"),
}

# --- Risk ---
RISK_PER_TRADE = 0.01    # 1% of account per trade
MIN_RR = 2.0             # minimum reward:risk to take a setup
