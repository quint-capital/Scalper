# Quint Capital V75 V3.11 — Edge Research Edition

**Analysis/paper research only. No broker orders are sent.** This package builds on the reversed-signal M15/M5/M1 strategy. It deliberately preserves the signal engine while adding stronger measurement so we do not tune rules blindly.

## What is new

- Records each trade's original/source direction and emitted/reversed direction.
- Records M1/M5/M15 volatility labels and market-regime classification for stratified analysis.
- Tracks maximum favorable excursion (MFE) and maximum adverse excursion (MAE), expressed in R, while a simulated trade is open.
- Reports gross results and a user-configurable cost sensitivity (`--cost-r`, default 0.03R per resolved trade). This is a sensitivity assumption, not a verified Deriv cost quote.
- Produces chronological 70%/30% development/holdout statistics, plus results grouped by regime and M5 volatility. The holdout is diagnostic only; do not optimize to it.
- Keeps M15/M5/M1 as the only strategy timeframes and maintains reversed BUY/SELL setup direction.
- Remains paper-only; no broker order API is called.

## Run on Railway

Use the service start command:

```bash
python historical_tick_backtest.py --days 7 --symbol R_75 --cost-r 0.03
```

For a longer first diagnostic, if Deriv history access supports it:

```bash
python historical_tick_backtest.py --days 14 --symbol R_75 --cost-r 0.03
```

Output is written to `backtest_results/`: raw tick CSV, trade-level CSV and JSON summary. Download/save these outputs before redeploying if the service filesystem is ephemeral.

## Important limitations

1. A seven-day sample may be too small to establish an edge. The 70/30 split can be inconclusive if the holdout has few trades.
2. MFE/MAE and exits are simulated against the downloaded ticks. Entry fill is assumed at the engine's setup entry price, not a separately verified executable quote; price slippage and latency are not fully modeled.
3. `--cost-r` is a user-provided per-trade cost in risk units, not a measured Deriv fee. Test multiple values rather than treating the default as factual.
4. The strategy rules are not claimed to be more profitable merely because diagnostics improved. First compare expectancy, profit factor, drawdown and sample size, then make one evidence-led strategy change at a time.
5. Unresolved positions at the end are reported separately and excluded from resolved-trade metrics.
