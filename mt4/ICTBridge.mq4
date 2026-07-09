//+------------------------------------------------------------------+
//| ICTBridge.mq4                                                     |
//| File bridge between the Python ICT bot and MetaTrader 4.          |
//|                                                                   |
//| Attach to the US30 M5 chart. Every 2 seconds it:                  |
//|   1. exports the last completed chart bars   -> ict_bars.csv      |
//|   2. exports account/position state          -> ict_status.csv    |
//|   3. executes new commands from Python       <- ict_commands.csv  |
//|      and logs the outcome                    -> ict_results.csv   |
//|                                                                   |
//| SAFETY: InpEnableTrading is FALSE by default - the EA only logs   |
//| what it would do. Flip it to true (ideally on a DEMO account      |
//| first) to let it place real orders. Orders always carry the       |
//| stop-loss and take-profit computed by the bot, one position at    |
//| a time, hard lot cap via InpMaxLots.                              |
//+------------------------------------------------------------------+
#property strict

input string InpBarsFile       = "ict_bars.csv";     // exported chart bars
input string InpStatusFile     = "ict_status.csv";   // exported account state
input string InpCommandFile    = "ict_commands.csv"; // commands from Python
input string InpResultFile     = "ict_results.csv";  // execution results log
input int    InpMagic          = 20260709;           // magic number for bot orders
input bool   InpEnableTrading  = false;              // false = dry run (log only)
input double InpMaxLots        = 5.0;                // hard cap on order size
input int    InpSlippagePoints = 30;                 // max slippage (points)
input int    InpBarsToExport   = 600;                // completed bars to export
input int    InpStaleSeconds   = 120;                // ignore commands older than this

int lastProcessedId = 0;

string GvName() { return "ICT_LASTCMD_" + Symbol() + "_" + IntegerToString(InpMagic); }

int OnInit()
{
   // survive EA/terminal restarts without re-executing old commands
   if(GlobalVariableCheck(GvName()))
      lastProcessedId = (int)GlobalVariableGet(GvName());
   EventSetTimer(2);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason) { EventKillTimer(); }

void OnTimer()
{
   ExportBars();
   ExportStatus();
   ProcessCommands();
}

//+------------------------------------------------------------------+
int BotOrderTicket()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES)) continue;
      if(OrderMagicNumber() != InpMagic) continue;
      if(OrderSymbol() != Symbol()) continue;
      if(OrderType() > OP_SELL) continue; // market orders only
      return(OrderTicket());
   }
   return(-1);
}

//+------------------------------------------------------------------+
void ExportBars()
{
   int fh = FileOpen(InpBarsFile, FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(fh == INVALID_HANDLE) return;

   // $ move per point per 1.0 lot, so Python can size positions
   double pointValue = MarketInfo(Symbol(), MODE_TICKVALUE)
                       * (Point / MarketInfo(Symbol(), MODE_TICKSIZE));

   FileWriteString(fh, StringFormat(
      "meta,%s,%d,%d,%d,%.5f,%.2f,%.2f,%.2f\n",
      Symbol(), Period(),
      (int)TimeCurrent(), (int)TimeGMT(),   // lets Python derive UTC offset
      pointValue,
      MarketInfo(Symbol(), MODE_MINLOT),
      MarketInfo(Symbol(), MODE_MAXLOT),
      MarketInfo(Symbol(), MODE_LOTSTEP)));

   int last = MathMin(InpBarsToExport, Bars - 1);
   for(int i = last; i >= 1; i--)   // shift 1 = newest COMPLETED bar
      FileWriteString(fh, StringFormat("%d,%.2f,%.2f,%.2f,%.2f\n",
         (int)Time[i], Open[i], High[i], Low[i], Close[i]));
   FileClose(fh);
}

//+------------------------------------------------------------------+
void ExportStatus()
{
   int fh = FileOpen(InpStatusFile, FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(fh == INVALID_HANDLE) return;
   FileWriteString(fh, StringFormat("balance,%.2f\n", AccountBalance()));
   FileWriteString(fh, StringFormat("equity,%.2f\n", AccountEquity()));
   FileWriteString(fh, StringFormat("currency,%s\n", AccountCurrency()));
   FileWriteString(fh, StringFormat("trading_enabled,%d\n", InpEnableTrading ? 1 : 0));
   FileWriteString(fh, StringFormat("last_command_id,%d\n", lastProcessedId));
   FileWriteString(fh, StringFormat("time_gmt,%d\n", (int)TimeGMT()));

   int ticket = BotOrderTicket();
   if(ticket >= 0 && OrderSelect(ticket, SELECT_BY_TICKET))
   {
      FileWriteString(fh, "position,1\n");
      FileWriteString(fh, StringFormat("ticket,%d\n", ticket));
      FileWriteString(fh, StringFormat("direction,%s\n",
                      OrderType() == OP_BUY ? "long" : "short"));
      FileWriteString(fh, StringFormat("lots,%.2f\n", OrderLots()));
      FileWriteString(fh, StringFormat("entry,%.2f\n", OrderOpenPrice()));
      FileWriteString(fh, StringFormat("sl,%.2f\n", OrderStopLoss()));
      FileWriteString(fh, StringFormat("tp,%.2f\n", OrderTakeProfit()));
      FileWriteString(fh, StringFormat("profit,%.2f\n",
                      OrderProfit() + OrderSwap() + OrderCommission()));
   }
   else
      FileWriteString(fh, "position,0\n");
   FileClose(fh);
}

//+------------------------------------------------------------------+
void ProcessCommands()
{
   if(!FileIsExist(InpCommandFile)) return;
   int fh = FileOpen(InpCommandFile, FILE_READ|FILE_TXT|FILE_ANSI);
   if(fh == INVALID_HANDLE) return;
   string lastLine = "";
   while(!FileIsEnding(fh))
   {
      string line = FileReadString(fh);
      if(StringLen(line) > 3) lastLine = line;
   }
   FileClose(fh);
   if(lastLine == "") return;

   // command format: id,issued_gmt,action[,direction,lots,sl,tp]
   string parts[];
   if(StringSplit(lastLine, ',', parts) < 3) return;
   int id = (int)StringToInteger(parts[0]);
   if(id <= lastProcessedId) return;

   MarkProcessed(id);   // consume even on failure - Python re-issues if needed

   int issued = (int)StringToInteger(parts[1]);
   string action = parts[2];

   if(TimeGMT() - issued > InpStaleSeconds)
   { LogResult(id, "skipped", "stale command"); return; }

   if(action == "open" && ArraySize(parts) >= 7)
   {
      string dir  = parts[3];
      double lots = NormalizeDouble(StringToDouble(parts[4]), 2);
      double sl   = NormalizeDouble(StringToDouble(parts[5]), Digits);
      double tp   = NormalizeDouble(StringToDouble(parts[6]), Digits);

      if(lots <= 0 || lots > InpMaxLots)
      { LogResult(id, "rejected", "lots outside 0..InpMaxLots"); return; }
      if(BotOrderTicket() >= 0)
      { LogResult(id, "skipped", "already in a position"); return; }
      if(!InpEnableTrading)
      { LogResult(id, "dry_run", StringFormat(
           "would open %s %.2f lots sl=%.1f tp=%.1f", dir, lots, sl, tp)); return; }

      RefreshRates();
      int type = (dir == "long") ? OP_BUY : OP_SELL;
      double price = (type == OP_BUY) ? Ask : Bid;
      int ticket = OrderSend(Symbol(), type, lots, price, InpSlippagePoints,
                             sl, tp, "ICT bot", InpMagic, 0, clrDodgerBlue);
      if(ticket < 0)
         LogResult(id, "error", "OrderSend failed: " + IntegerToString(GetLastError()));
      else
         LogResult(id, "opened", StringFormat(
            "ticket %d %s %.2f lots @ %.1f", ticket, dir, lots, price));
   }
   else if(action == "close")
   {
      int ticket = BotOrderTicket();
      if(ticket < 0) { LogResult(id, "skipped", "no open position"); return; }
      if(!InpEnableTrading)
      { LogResult(id, "dry_run", "would close ticket " + IntegerToString(ticket)); return; }
      if(OrderSelect(ticket, SELECT_BY_TICKET))
      {
         RefreshRates();
         double price = (OrderType() == OP_BUY) ? Bid : Ask;
         if(!OrderClose(ticket, OrderLots(), price, InpSlippagePoints, clrOrange))
            LogResult(id, "error", "OrderClose failed: " + IntegerToString(GetLastError()));
         else
            LogResult(id, "closed", "ticket " + IntegerToString(ticket));
      }
   }
   else
      LogResult(id, "skipped", "unknown command: " + action);
}

//+------------------------------------------------------------------+
void MarkProcessed(int id)
{
   lastProcessedId = id;
   GlobalVariableSet(GvName(), id);
}

void LogResult(int id, string outcome, string detail)
{
   int fh = FileOpen(InpResultFile, FILE_READ|FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(fh == INVALID_HANDLE)
      fh = FileOpen(InpResultFile, FILE_WRITE|FILE_TXT|FILE_ANSI);
   if(fh == INVALID_HANDLE) return;
   FileSeek(fh, 0, SEEK_END);
   FileWriteString(fh, StringFormat("%d,%d,%s,%s\n",
                   id, (int)TimeGMT(), outcome, detail));
   FileClose(fh);
   Print("ICTBridge: ", outcome, " - ", detail);
}
//+------------------------------------------------------------------+
