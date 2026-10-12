# Quint Capital V75 Scalping Monitor v3.7

**Analysis-only. No trade execution.** This package adapts the uploaded Quint Capital V75 v3.5 engine for short-horizon scalping research.

## Scalping design
- M1 is the entry/monitoring timeframe; M5 and M15 provide short-term context. Higher timeframes remain available as background filters.
- Structural local stop-loss based on M1/M5 swings and volatility.
- TP1 is structure-aware with a 0.40R minimum room by default (or labelled 0.50R fallback when no confirmed opposing M5 pivot exists); TP2 is a 1.25R milestone and TP3 is a 1.75R milestone.
- Continuation entries have a separate M1 displacement/BOS/MSS confirmation path. Extension, exhaustion, adverse microstructure and stop-risk protections remain active.
- One active setup at a time and one setup per structural move.
- Live tick feed is aggregated into M1 candles; setups are evaluated using completed candles.
- Results and analysis are stored in separate `v75_scalp_*` files under `/app/data`, avoiding mixing new scalping outcomes with the prior v3.5 journals. Existing market-history file is retained.

## Deploy
1. Upload the files in this folder to your GitHub repo.
2. In Railway, mount the existing persistent volume at `/app/data`.
3. Set `DERIV_SYMBOL=R_75` if needed.
4. Set the Railway variable `DERIV_APP_ID` to your own registered Deriv application ID (create/register one through Deriv API settings). The default `1089` ID is for testing only. The monitor builds the official endpoint `wss://ws.derivws.com/websockets/v3?app_id=YOUR_ID`. You can override the full endpoint with `DERIV_WS_URL` if needed.
5. Default bootstrap is 10,000 M1 candles. Override with `HISTORY_BOOTSTRAP_CANDLES`.
6. Deploy and inspect logs for a successful WebSocket connection, historical candles and `[HEARTBEAT] Live ticks flowing`.

## Monitoring caveats
- HTTP 520 means the server/gateway rejected or failed the handshake; changing the URL is a test, not a guarantee.
- No live connection means no valid signals or performance observations.
- Simulated OHLC outcomes can be ambiguous when stop and target are touched in the same M1 candle. Ambiguous cases are not counted as wins/losses.
- No strategy is presumed profitable. Monitor enough completed setups and review results before considering changes.
- `SCALP_TP1_RR` (default `0.75`) and `SCALP_TP1_MAX_RR` (default `1.00`) tune the first target.


## If Railway logs show HTTP 520 on the WebSocket handshake

- Confirm `DERIV_APP_ID` is your own registered Deriv app ID, then redeploy.
- Keep the default official endpoint first; do not assume switching to another legacy hostname will fix an HTTP 520.
- If a registered ID still returns HTTP 520, test the same endpoint from a different network/runtime and check Deriv service status. HTTP 520 is returned during the handshake, before this monitor sends a market-data request, so it is not caused by the scalping signal rules.
- Confirm the Railway Volume is attached to this exact service with mount path `/app/data`. A correctly attached volume should provide `RAILWAY_VOLUME_MOUNT_PATH` at runtime. The marker file by itself does not prove persistence.


## v1.3 direction-aware entry experiment
- Evaluates bullish and bearish structural transitions independently; a single bearish clue no longer forces the transition direction.
- Before a setup can be accepted, M1 must show at least two counter-direction candles in the prior five candles, followed by a close through the recent three-candle range in the proposed direction.
- The entry gate status is included in the analysis output as `entry_gate` for diagnostics.
- Stop-loss, risk-cap, TP1/TP2/TP3 and geometry calculations are unchanged from the supplied baseline.
- This is an experimental filter, not a claim of improved profitability. Compare a meaningful sample of completed setups against the previous version.

## v3.7 more responsive entry experiment
- See `CHANGELOG_V3_7_MORE_RESPONSIVE_ENTRIES.md`.
- Default `SCALP_TP1_RR` is now 0.40; `SCALP_TP1_MAX_RR` remains 1.00.
- Analysis-only: no broker order execution.
