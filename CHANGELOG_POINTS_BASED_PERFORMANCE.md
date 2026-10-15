# Points-based performance reporting

- Added gross realized profit points, gross realized loss points, net points, and average net points per resolved trade.
- TP1 contributes `abs(TP1 - entry)` to gross profit points; SL contributes `abs(entry - SL)` to gross loss points.
- Net points = gross profit points - gross loss points.
- Same-candle TP/SL ambiguous outcomes are excluded from realized point totals.
- Existing planned RR and realized R remain available as secondary diagnostics; negative net R is not an individual trade's RR.
- Legacy setup records are supported when they contain entry, SL, TP1, and a resolved outcome.
- Point units are raw V75 index-price units, not cash P/L or a broker-specific tick-value calculation.
- Analysis-only; no execution behavior changed.
