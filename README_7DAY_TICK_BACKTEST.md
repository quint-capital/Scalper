# Historical tick backtest

For the V3.11 research build, see `README_V3_11_EDGE_RESEARCH.md`. The tool downloads Deriv historical ticks for R_75 by default, builds M1/M5/M15 candles, replays the included strategy engine on completed candles, and checks simulated SL/TP against subsequent ticks. It sends no broker orders.

Run: `python historical_tick_backtest.py --days 7 --symbol R_75 --cost-r 0.03`

Outputs in `backtest_results/`: raw ticks CSV, trade CSV, and JSON summary with gross/net performance, chronological holdout diagnostics, market-regime/volatility breakdown, and MFE/MAE. The configured cost is an assumed sensitivity input, not a verified quote. Seven days alone cannot prove future profitability.
