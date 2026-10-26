# V3.12 — Continuous live paper monitor

- Railway start command explicitly launches `python main.py`, not the seven-day historical backtester.
- Uses live Deriv `R_75` ticks and continuously evaluates completed M1 candles with M15/M5/M1 strategy context.
- Keeps reverse-signal logic and analysis-only safeguards; no real broker order code added.
- Uses new isolated V3.12 history, analysis, setups, and active-trade files for a fresh paper-trade count.
- Fixed journal setup creation to mark H4/H1/M30 as `NOT USED` rather than indexing timeframes intentionally absent from this model.
- Deployment/connectivity and profitability are not claimed as verified until Railway logs and accumulated paper results confirm them.
