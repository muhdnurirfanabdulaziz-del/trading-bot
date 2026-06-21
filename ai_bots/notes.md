# Trading Bot Strategy Notes

## Moving-average crossover
The bot compares a short moving average (10 days) against a long moving average
(50 days). When the short MA rises above the long MA it emits a BUY signal; when
the short MA falls below the long MA it emits a SELL signal; otherwise it holds.

## What a buy signal means
A BUY signal means short-term momentum is turning upward relative to the longer
trend. It is not a guarantee — crossovers can produce false signals in sideways
("choppy") markets.

## What a sell signal means
A SELL signal means short-term momentum is weakening relative to the longer
trend. The bot would exit or avoid the position.

## Risk management
This bot is for paper trading and education only. It does not size positions,
set stop-losses, or account for fees and slippage. Never trade real money based
solely on these signals.

## Tickers and windows
The default ticker is AAPL with a 10-day short window and a 50-day long window.
Shorter windows react faster but produce more false signals.
