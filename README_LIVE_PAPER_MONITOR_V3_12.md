# Quint Capital V75 Reversed V3.12 — Continuous Live Paper Monitor

**Runtime mode:** continuous monitoring of live Deriv V75 (`R_75`) ticks, M15/M5/M1 analysis, reversed BUY/SELL signals, and simulated paper setups. **No broker orders, no MT5, no real-money execution.**

## What happens after deployment

1. Railway runs `python main.py` continuously (not the historical backtester).
2. The service connects to the public Deriv WebSocket and subscribes to live `R_75` ticks.
3. It bootstraps M1 candles as needed, builds M5/M15 candles, and analyses each completed M1 candle.
4. When the engine accepts a setup, it creates a paper trade with entry, SL and TP1, then tracks the simulated outcome on later M1 candles.
5. It appends analysis snapshots and saves active/closed paper trades to a separate V3.12 journal namespace.

## Fresh trade history

The V3.12 default files are isolated from earlier journals:

- `/app/data/qute_v75_reversed_v3_12_live_history.json`
- `/app/data/qute_v75_reversed_v3_12_live_analysis.jsonl`
- `/app/data/qute_v75_reversed_v3_12_live_setups.json`
- `/app/data/qute_v75_reversed_v3_12_live_active.json`

New setup history begins at zero when these files do not already exist. Keep a Railway persistent Volume mounted at `/app/data` so records survive restarts. If Railway has old V3.12 files on that volume, remove/rename only those V3.12 files to reset again; do not delete other project data.

## Railway deployment

1. Upload this folder's contents to a dedicated GitHub repository, or replace the code in the intended paper-monitor service. Do not point the live service at `historical_tick_backtest.py`.
2. Set the Railway start command to `python main.py` (this package's `railway.json` also declares it).
3. Mount a persistent Volume at `/app/data`.
4. Deploy and check logs for `CONTINUOUS LIVE PAPER MONITOR`, `WebSocket connected`, `First live tick received`, `Live stream active`, and periodic `[HEARTBEAT]` messages.
5. Confirm `[STORAGE]` paths and that `qute_v75_reversed_v3_12_live_setups.json` starts empty.

## Important limitations

- This is simulated paper trading, not an order-execution bot.
- A setup is only created when the strategy's filters accept a signal; it will not force trades just to increase the count.
- Paper fills use the strategy's calculated entry and M1 OHLC outcomes; actual execution, spread, latency and slippage are not reproduced fully.
- Deployment has not been performed from this chat. Deriv connectivity and live journaling must be confirmed in your Railway logs after you deploy.
- Do not infer profitability from successful startup. Collect a meaningful sample and evaluate net expectancy and drawdown.
