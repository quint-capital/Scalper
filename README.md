# V2 Responsive Inverse Experiment — important

This ZIP is the separate `QUTE_V75_IMPROVED_REVERSED_V2_RESPONSIVE` analysis-only experiment. It intentionally reverses source BUY/SELL setup direction. It uses isolated default V2 history/journal paths and does not execute trades. See `CHANGELOG_IMPROVED_REVERSED_V2_RESPONSIVE.md` for the exact gate changes and validation.

# Quint Capital V75 — Improved Reversed-Signal V1

**Analysis-only / paper tracking. No broker orders, MT5 connection, or execution code.** This is a separate experimental version based on the uploaded reversed-signal package. The original system and its files must remain untouched.

## Direction audit

The source first generates a source-direction setup and then reverses the emitted direction (BUY ↔ SELL). The final setup geometry is calculated for the emitted direction; this is not a simple SL/TP swap. The report now states that explicitly. This version preserves that reversed-signal experiment and adds guards around the emitted trade.

## Added protections

1. **Market-regime classification:** labels broad conditions as bullish trend, bearish trend, trend with countertrend pullback, or range/transition/mixed. Range/transition candidates are blocked rather than forced into trades.
2. **Stronger confirmation:** requires a completed M1 candle in the emitted trade direction, an M1 MSS/BOS/displacement trigger in that direction, and M5 directional support.
3. **Repeated-entry and loss protection:** one active paper setup at a time and one setup per setup cycle remain in place. After a stop-out, new entries are paused for the configured cooldown; a consecutive-loss streak triggers a longer temporary pause.
4. **Structure-based SL/TP audit:** preserves swing/ATR stop construction and opposing-swing targets, then rejects wrong-side SL/TP, stops wider than the configured M5-ATR cap, or targets below minimum RR. It does not extend targets just to inflate RR.
5. **Signal and journal audit:** explicit reversed direction, regime and confirmation diagnostics are journaled. Setup IDs are versioned and each setup stores its source and emitted direction.

These are experimental filters, not proven profitability improvements. Strict confirmation can reduce the number of trades; compare net expectancy and drawdown, not win rate alone.

## Separate persistent files

Default files under `/app/data`:
- `qute_v75_improved_reversed_v2_responsive_history.json`
- `qute_v75_improved_reversed_v2_responsive_analysis.jsonl`
- `qute_v75_improved_reversed_v2_responsive_setups.json`
- `qute_v75_improved_reversed_v2_responsive_active.json`
- `.quint_v75_improved_reversed_v2_responsive_volume_marker`

Configurable controls: `POST_LOSS_COOLDOWN_MINUTES` (default 5), `MAX_CONSECUTIVE_LOSSES` (default 2), `SCALP_TP1_MIN_RR` (default 0.75), `MAX_STOP_ATR_M5` (default 2.50). `REV2_HISTORY_FILE`, `REV2_ANALYSIS_JOURNAL_FILE`, `REV2_SETUP_JOURNAL_FILE`, `REV2_ACTIVE_SETUPS_FILE`, and `REV2_STORAGE_MARKER_FILE` can override the paths. Do not point these at the original system's files.

## Deploy separately

1. Create a new GitHub repository named `Quint-Capital-V75-Improved-Reversed-V2-Responsive` and upload this folder's contents.
2. Create a new Railway service from that repository; do not redeploy over the existing service.
3. Mount a persistent volume at `/app/data`.
4. Use the same working Deriv symbol/WebSocket configuration.
5. Verify startup logs identify `IMPROVED REVERSED-SIGNAL V2 RESPONSIVE` and storage paths contain `improved_reversed_v2_responsive`.

## Evaluation

Keep the existing service unchanged and compare on the same period. Aim for 50–100 resolved paper setups if practical. Compare net R, win rate, profit factor, maximum drawdown, number of blocked candidates, MFE/MAE, planned RR, and ambiguous same-candle outcomes. Paper outcomes use M1 OHLC; if SL and TP are touched within one candle, outcome remains ambiguous.


## V3.9 strategy repair
See `CHANGELOG_V3.9_STRATEGY_REPAIR.md`. This build adds reversed-direction confirmation, transition-only countertrend admission, conservative structural stops, a 1.25R maximum TP1 cap, and a fresh isolated V3.9 journal/history namespace. Analysis-only; no broker orders.


## V3.9 balanced frequency/quality
See `CHANGELOG_V3_9_BALANCED_FREQUENCY.md`. This version uses a 2-of-3 reversed-direction confirmation and a balanced multi-timeframe regime path to admit more candidate setups while retaining structural and geometry safeguards. Analysis-only; no broker orders.
