# Quint Capital V75 Scalping Monitor v1.0

**Analysis only. No trade execution.** The monitor listens to public Deriv ticks, builds closed M1 candles, checks completed M5/M15 context, emits simulated BUY/SELL setups, and records hypothetical outcomes.

## Files
- `main.py`: complete single-file monitor and signal logic.
- `requirements.txt`: WebSocket dependency.
- `railway.json`: Railway startup configuration.

## Deploy
1. Replace the relevant files in your GitHub repository with these files.
2. Commit and allow Railway to redeploy.
3. Keep the persistent Railway volume mounted at `/app/data`.
4. Set `DERIV_APP_ID` to your registered Deriv app ID if you have one. The code defaults to public test app ID `1089` if no app ID is set.
5. Optional: set `DERIV_SYMBOL=R_75` and `DATA_DIR=/app/data`.

## Output
- `/app/data/scalping/v75_scalping_setups.jsonl`: one JSON record per setup update/closure.
- `/app/data/scalping/v75_scalping_state.json`: latest summary and any open simulated setup.

## Important limits
- Signals require enough live closed candles to warm up the indicators (about 100 M1 candles, so roughly 100 minutes after a cold start). No historical bootstrap is required.
- If Deriv rejects the WebSocket handshake (for example HTTP 520), the monitor cannot receive prices and therefore cannot generate or monitor signals. It retries with backoff; this is a connection problem, not a strategy result.
- Stop/target levels use M1 ATR(14). TP1/TP2/TP3 are 0.5R/1R/1.5R. A setup is closed when the first target/stop is touched or after 30 minutes. Outcomes are hypothetical and omit verified spread, slippage, and execution costs. Do not treat early results as evidence of profitability.
- This package does not place orders or connect to MT5.
