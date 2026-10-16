# Hybrid Exit Model v1

- Preserves all entry qualification, direction selection, confirmation, and setup-cycle logic.
- Reworks only stop/target geometry in `engine.py`.
- Stop loss: uses the more conservative of M1 and M5 swing invalidation candidates, with ATR buffers on the swing levels and an ATR-based minimum risk distance.
- Take profit: targets 1.50R by default, capped at 90% of the nearest confirmed opposing M5 pivot when one exists. If no usable opposing pivot exists, target is the larger of 1.50R and 1.25 × M5 ATR.
- `SCALP_TP1_TARGET_RR` can tune the target multiple (clamped to 0.75R–3.0R); default 1.50R.
- Analysis-only; no broker order execution.
- This is a candidate model, not a claim of improved performance. Evaluate on chronological out-of-sample candles and include costs/slippage where applicable.
