# Exit Intelligence V2 — paper-only experiment

- Base: `QUTE_DOUBLE_REVERSED_FRESH_LOGS_V1.zip`.
- Preserves the existing strategy's signal/direction, entry calculation, Deriv R_75 WebSocket connection, storage layout, Railway configuration and startup method.
- Changes exits only at journal capture: keeps the existing stop-loss and sets the take-profit to at least 1.0R (configurable with `EXIT_V2_MIN_TP_RR`, default `1.0`). If the prior target is farther away, it is retained.
- Adds per-setup realized net points and R, plus aggregate gross profit points, gross loss points, and net profit/loss points to the existing performance output.
- If SL and TP are both inside the same M1 candle, the outcome remains ambiguous and is excluded from realized point totals rather than guessing order.
- Analysis/paper journal only. No broker order execution.
