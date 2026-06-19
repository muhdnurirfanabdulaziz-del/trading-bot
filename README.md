# trading-bot

A simple algorithmic trading bot skeleton in Python.

## Features

- Fetches live price data from a public API
- Implements a basic moving-average crossover strategy
- Paper-trades (no real money at risk)

## Setup

```bash
pip install -r requirements.txt
python main.py
```

## Configuration

Edit `config.py` to set your ticker symbol and moving-average windows.

## Strategy

The bot buys when the short moving average crosses above the long moving average,
and sells when it crosses below.

## Disclaimer

This is for educational purposes only. Do not use with real funds.
