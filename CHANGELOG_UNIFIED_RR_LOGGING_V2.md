# Unified QUTE strategy + RR analytics v2

- Standardized the user-facing strategy name to `QUTE V75 SCALPER`; BUY/SELL are directions, not different strategy types.
- Added planned RR and reward-distance fields to every setup record and setup console message.
- Added realized R per resolved setup, with TP1 = planned RR, SL = -1R, and same-candle TP/SL = ambiguous (excluded from resolved stats).
- Added average/median planned RR, net R, average realized R, R-based profit factor, and average MFE/MAE to the aggregate performance report.
- Switched to v2 journal filenames to avoid mixing prior experiment-specific counters with the unified strategy report.
- Paper-only; no broker order execution was added.
