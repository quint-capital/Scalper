# Structure-led exits v1

- Entry direction, trigger gates, and entry confirmations are unchanged.
- Stop-loss remains hybrid M1/M5 swing invalidation with ATR buffers and a minimum volatility-based distance.
- TP1 now targets the nearest confirmed opposing M5/M15 swing objective and front-runs it by an ATR buffer; if no confirmed objective exists, an explicitly labeled ATR fallback is used.
- M1/M5 momentum alignment affects target reachability: when neither timeframe supports the proposed direction, the target is conservatively shortened rather than stretched.
- Setups are skipped if the structural objective offers less than `SCALP_TP1_MIN_RR` (default 0.65R). RR is a viability check; it does not manufacture a farther target.
- The journal already labels same-M1-candle SL/TP collisions as ambiguous.
- Analysis-only. No broker order execution was added.

This is a logic change, not evidence of profitability. Replay the same historical entries and compare net R, profit factor, win rate, drawdown, and ambiguous outcomes before accepting it.
