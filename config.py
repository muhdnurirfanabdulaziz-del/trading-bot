# --- Instrument ---
TICKER = "US30"          # Dow Jones Industrial Average CFD/index
YF_SYMBOL = "^DJI"       # yfinance proxy for US30 (Dow Jones index)
POINT_VALUE = 1.0        # $ per point per unit

# --- Live data feed ---
DATA_INTERVAL = "5m"     # candle size for live ICT analysis
DATA_PERIOD = "5d"       # history window (yfinance caps 5m data at 60d)
REFRESH_SECONDS = 300    # poll interval in --live mode (one M5 candle)

# --- Legacy moving-average strategy ---
SHORT_WINDOW = 10
LONG_WINDOW = 50
VOLUME_WINDOW = 20
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

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

# --- Signal confluence ---
# How many bars a sweep or structure event stays "fresh" as confluence
# (36 x M5 = 3 hours).
SIGNAL_FRESHNESS_BARS = 36
# Narrative conditions required on top of kill zone + OB/FVG tap:
# 1 = liquidity sweep OR structure break (trades regularly)
# 2 = sweep AND structure break (strict A+ only - rarely trades)
MIN_CONFLUENCE = 1
# Bars to wait before signalling the same direction again.
SIGNAL_COOLDOWN_BARS = 12

# --- Risk / paper trading ---
ACCOUNT_BALANCE = 10_000.0   # starting paper balance
RISK_PER_TRADE = 0.01        # 1% of account per trade
MIN_RR = 2.0                 # minimum reward:risk to take a setup
PAPER_STATE_FILE = "paper_state.json"
TRADE_LOG_FILE = "trades.csv"
