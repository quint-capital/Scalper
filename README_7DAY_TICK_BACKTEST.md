# Seven-day historical tick backtest (V3.9)

This add-on downloads Deriv historical ticks for the configured symbol (default `R_75`), builds M1/M5/M15/M30/H1/H4 candles, runs the included V3.9 `engine.py` on completed M1 bars, and checks SL/TP against the downloaded tick sequence. It is analysis-only and sends no broker orders.

## Run

```bash
pip install -r requirements.txt
python historical_tick_backtest.py --days 7 --symbol R_75
```

Outputs in `backtest_results/`:
- Raw ticks CSV (`*_ticks.csv`)
- Resolved trade-by-trade CSV (`*_trades.csv`)
- Summary JSON (`*_summary.json`) with win rate, net R, profit factor, average R/trade, and maximum drawdown.

Settings: `DERIV_SYMBOL`, `DERIV_WS_URL`, `BACKTEST_DAYS`, `TICK_BATCH_SIZE`, `BACKTEST_OUTPUT_DIR`.

## Important limitations

- This is a historical simulation, not proof of future profitability.
- It uses the packaged V3.9 engine, but does not recreate every live runtime detail, network delay, journal state, or deployment setting.
- Entry is evaluated at completed M1 closes; the strategy engine may internally use its latest candle as the decision candle. Audit the first/last bar timing if using results for decisions.
- Exit checks use tick history and a conservative stop-first rule if both levels would be considered hit at the same sampled tick. A still-open trade at the end is reported as unresolved and excluded from resolved performance.
- Costs/slippage are not modeled; add a realistic cost model before concluding the system is profitable.
- Deriv history retention and API behavior can vary. If pagination fails to advance, the script stops rather than pretending it downloaded a complete sample.
- A seven-day sample may contain too few trades for a reliable conclusion. Prefer longer out-of-sample validation after this initial test.
