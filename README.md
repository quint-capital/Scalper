# Quint Capital V75 Double-Reversed Baseline Paper Monitor

**Analysis-only. No broker orders.** This paper-only experiment reverses the previously uploaded source transformation a second time. Therefore it restores the source BUY/SELL direction and source SL/TP1 geometry. It is a baseline comparison, not a new independent reversal strategy. TP2 and TP3 are removed; TP1 is the only target.

## Scalping design
- M1 is the entry/monitoring timeframe; M5 and M15 provide short-term context. Higher timeframes remain available as background filters.
- Source geometry uses the original M1/M5 structural stop and original TP1; these two levels are swapped for the source setup.
- The source setup has exactly one target, TP1. No TP2/TP3 levels or RR target gates are used.
- Continuation entries have a separate M1 displacement/BOS/MSS confirmation path. Extension, exhaustion, adverse microstructure and stop-risk protections remain active.
- One active setup at a time and one setup per structural move.
- Live tick feed is aggregated into M1 candles; setups are evaluated using completed candles.
- Results and analysis use fresh, versioned `v75_double_reversed_fresh_*_v1` journal files under `/app/data`, so prior outcomes are not loaded. Existing market-history file is retained.

## Deploy
1. Upload the files in this folder to your GitHub repo.
2. In Railway, mount the existing persistent volume at `/app/data`.
3. Set `DERIV_SYMBOL=R_75` if needed.
4. Keep the connection configuration from the supplied working monitor: it tries `wss://api.derivws.com/trading/v1/options/ws/public` first, then `wss://ws.binaryws.com/websockets/v3`. Override the first URL with `DERIV_WS_URL` only if you have a known working endpoint.
5. Default bootstrap is 10,000 M1 candles. Override with `HISTORY_BOOTSTRAP_CANDLES`.
6. Deploy and inspect logs for a successful WebSocket connection, historical candles and `[HEARTBEAT] Live ticks flowing`.

## Monitoring caveats
- HTTP 520 means the server/gateway rejected or failed the handshake; changing the URL is a test, not a guarantee.
- No live connection means no valid signals or performance observations.
- Simulated OHLC outcomes can be ambiguous when stop and target are touched in the same M1 candle. Ambiguous cases are not counted as wins/losses.
- No strategy is presumed profitable. Monitor enough completed setups and review results before considering changes.
- The source TP1 geometry still uses `SCALP_TP1_MAX_RR` as an upper cap; the source result does not optimize or filter on reward-to-risk.


## If Railway logs show HTTP 520 on the WebSocket handshake

- Confirm `DERIV_APP_ID` is your own registered Deriv app ID, then redeploy.
- Keep the default official endpoint first; do not assume switching to another legacy hostname will fix an HTTP 520.
- If a registered ID still returns HTTP 520, test the same endpoint from a different network/runtime and check Deriv service status. HTTP 520 is returned during the handshake, before this monitor sends a market-data request, so it is not caused by the scalping signal rules.
- Confirm the Railway Volume is attached to this exact service with mount path `/app/data`. A correctly attached volume should provide `RAILWAY_VOLUME_MOUNT_PATH` at runtime. The marker file by itself does not prove persistence.


## v1.3 direction-aware entry experiment
- Evaluates bullish and bearish structural transitions independently; a single bearish clue no longer forces the transition direction.
- Before a setup can be accepted, M1 must show at least two counter-direction candles in the prior five candles, followed by a close through the recent three-candle range in the proposed direction.
- The entry gate status is included in the analysis output as `entry_gate` for diagnostics.
- Source stop/target geometry is transformed by the source layer; the source journal tracks only SL and TP1.
- This is an experimental filter, not a claim of improved profitability. Compare a meaningful sample of completed setups against the previous version.

## v3.7 more responsive entry experiment
- See `CHANGELOG_V3_7_MORE_RESPONSIVE_ENTRIES.md`.
- The source setup does not use an RR acceptance threshold. The source TP1 distance still has the original maximum cap.
- Analysis-only: no broker order execution.


## Fresh log set

This package uses a new set of analysis, setup, and active-setup journal filenames. Historical market candles are preserved, but performance counters start fresh. See `CHANGELOG_FRESH_LOGS_V1.md`.
