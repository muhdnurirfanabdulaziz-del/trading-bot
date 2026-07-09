# Connecting the bot to MetaTrader 4

MT4 cannot be driven from Python directly, so the connection is a file
bridge: the `ICTBridge.mq4` Expert Advisor runs inside MT4 and talks to
the bot through four small files in the terminal's `MQL4\Files` folder.

```
MT4 (ICTBridge EA)                      Python bot (main.py --mt4)
  exports broker US30 M5 bars  ------>  ict_bars.csv      reads bars
  exports account & position   ------>  ict_status.csv    reads state
  executes orders              <------  ict_commands.csv  writes orders
  logs what it did             ------>  ict_results.csv   reads outcomes
```

The bot analyses your broker's actual US30 prices (not Yahoo's index),
and every order it sends carries its stop-loss and take-profit, sized so
a stop-out loses `RISK_PER_TRADE` (1%) of the account.

## Setup (once)

1. Open MT4 -> `File` -> `Open Data Folder` -> `MQL4` -> `Experts`, and
   copy `ICTBridge.mq4` there.
2. In MT4 press F4 (MetaEditor), open `ICTBridge.mq4`, press **Compile**
   (no errors expected), then close MetaEditor.
3. Back in MT4, open a **US30 chart** and set the timeframe to **M5**.
4. Drag `ICTBridge` from the Navigator onto that chart. In the dialog:
   - `Common` tab: tick **Allow live trading**.
   - `Inputs` tab: leave `InpEnableTrading = false` for the first session
     (dry run - it logs what it *would* do without placing orders).
5. Make sure the **AutoTrading** button in the MT4 toolbar is ON (green).
6. In the repo's `config.py`, set `MT4_FILES_DIR` to the `MQL4\Files`
   folder from step 1, e.g.
   `MT4_FILES_DIR = r"C:\Users\you\AppData\Roaming\MetaQuotes\Terminal\<long id>\MQL4\Files"`

## Run

```bash
python main.py --mt4
```

Each poll prints the broker time, balance, and position state. When a
setup fires you'll see `>>> SENT LONG 2.20 lots ...` and, from the EA,
`EA result: dry_run - would open long ...`.

## Going live

Test the loop on a **demo account with dry run** first, then re-attach
the EA with `InpEnableTrading = true` (still on demo), and only fund it
with real money once you're satisfied with the results. Safety rails:

- the EA refuses orders above `InpMaxLots` (and the bot has its own
  `MT4_MAX_LOTS` cap),
- one position at a time, identified by magic number `20260709`,
- commands older than `InpStaleSeconds` (120s) are ignored, so a
  stalled bot can't fire stale orders,
- every order carries the stop and target - nothing rides unprotected,
- closing the Python bot never abandons a position unprotected: the
  broker holds the SL/TP server-side.

## Troubleshooting

- `waiting for EA files...` - the EA isn't running (check the smiley
  face on the chart and that AutoTrading is on), or `MT4_FILES_DIR`
  points to the wrong folder.
- `EA chart is M15, expected M5` - switch the chart timeframe to M5.
- `OrderSend failed: 131` - lot size invalid for your broker; check
  the symbol's min/step lots in the MT4 symbol specification.
- US30 symbol names vary by broker (`US30`, `US30.cash`, `DJ30`...).
  Attach the EA to whichever chart your broker uses - the EA exports
  whatever symbol it sits on, no config needed.
