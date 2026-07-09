# trading-bot

An algorithmic trading bot for **US30** built around ICT / Smart Money Concepts,
running on live intraday data from yfinance (`^DJI`).

## Concepts implemented (`ict/` package)

- **Liquidity** (`ict/liquidity.py`) — the "fuel" that drives market moves.
  Swing highs cluster into buy-side liquidity pools (short-sellers' stops),
  swing lows into sell-side pools (long-traders' stops); equal highs/lows
  merge into stronger pools. Sweeps (a wick through a pool with a close back
  inside) are detected as stop-hunt fingerprints.
- **Fair Value Gaps** (`ict/fvg.py`) — three-candle imbalances left by
  impulsive moves. Gaps are tracked until touched and filled, with the
  consequent-encroachment (50%) level exposed.
- **Market Structure** (`ict/structure.py`) — fractal swing points mapped
  into **BOS** (continuation), **CHoCH** (first reversal warning), and
  **MSS** (a shift confirmed by displacement).
- **Order Blocks** (`ict/order_blocks.py`) — the last opposing candle before
  a displacement move, i.e. where institutions accumulated/distributed.
  Zones are tracked through mitigation and invalidation.
- **Kill Zones** (`ict/killzones.py`) — London Open (02:00–05:00),
  New York AM (08:30–11:00) and New York PM (13:30–16:00), in New York
  local time so EST/EDT is automatic.

## Strategy (`ict/strategy.py`)

The bot trades **day-long**. The hard requirement for a signal is price
tapping an unmitigated **order block** or unfilled **FVG** (which sets the
direction), plus enough of the two narrative conditions:

- a recent **liquidity sweep** on the opposite side,
- a recent **structure event** (BOS/CHoCH/MSS) confirming the direction.

Inside a **kill zone** `MIN_CONFLUENCE` (default 1) of the two suffices;
outside kill zones both are required (`OFF_ZONE_CONFLUENCE`) because
institutional flow is thinner off-hours. Set `KILL_ZONES_ONLY = True` to
restrict entries to kill zones, or `MIN_CONFLUENCE = 2` for strict
A+-only mode everywhere.

Targets prefer the nearest opposing liquidity pool, falling back to a fixed
`MIN_RR` (default 2R) target; sub-2R setups are discarded and a direction
won't re-fire within the cooldown window.

## MetaTrader 4 execution (`mt4/`)

`python main.py --mt4` trades through your MT4 terminal via the
`ICTBridge.mq4` Expert Advisor attached to your broker's US30 M5 chart:
the EA exports live broker candles and account state to files, the bot
runs the ICT engine on them and writes risk-sized orders back (stop and
take-profit always attached, one position at a time). The EA starts in
dry-run mode. Full setup guide: [mt4/README.md](mt4/README.md).

## Paper trading (`ict/paper.py`)

Live runs enter signals as simulated positions: size is computed so a stop
hit loses `RISK_PER_TRADE` (1%) of the account, positions are managed to
stop/target on each poll (a bar spanning both counts as a stop —
conservative), state survives restarts via `paper_state.json`, and every
closed trade is appended to `trades.csv`. No real orders are sent anywhere.

## Setup

```bash
pip install -r requirements.txt
python main.py                    # one-shot: live US30 candles -> full ICT report
python main.py --live             # keep polling every 5 minutes, announce new setups
python main.py --demo             # offline run on built-in synthetic US30 data
python main.py path/to/us30.csv   # or your own OHLC export (time,open,high,low,close)
```

Live runs also print the legacy MA + volume + MACD signal alongside the ICT
report. CSV timestamps are assumed UTC (naive) or may carry their own timezone.

## Configuration

Edit `config.py`: the data feed (`YF_SYMBOL`, candle interval/period, poll
rate), ICT tolerances in US30 points (equal-level tolerance, minimum FVG
size, displacement factor), kill-zone windows, swing lookback, and minimum
reward:risk.

## Tests

```bash
pip install pytest
python -m pytest tests/
```

## Disclaimer

This is for educational purposes only. Do not use with real funds.
