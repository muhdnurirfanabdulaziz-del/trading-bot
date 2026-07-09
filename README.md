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
- **Kill Zones** (`ict/killzones.py`) — London Open (02:00–05:00) and
  New York AM (08:30–11:00), in New York local time so EST/EDT is automatic.

## Strategy (`ict/strategy.py`)

A signal only fires when everything lines up on one bar:

1. Inside a **kill zone**,
2. after a recent **liquidity sweep** on the opposite side,
3. with a **structure event** (BOS/CHoCH/MSS) confirming the direction,
4. while price taps an unmitigated **order block** or unfilled **FVG**,
5. targeting the nearest opposing liquidity pool at **≥ 2R**.

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
