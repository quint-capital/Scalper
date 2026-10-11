# v1.2 — Entry-only pullback/resumption experiment

- Adds a strict completed-M1 pullback/resumption gate to reversal, continuation, and structural-transition entries.
- Requires at least two counter-direction candles in the preceding five M1 candles, then a directional current candle closing beyond the previous candle's high/low.
- Reports `ENTRY GATE`, pass/fail, and the reason in the analysis output.
- Does **not** change the stop-loss calculation, risk cap, TP1/TP2/TP3 levels, target geometry, journal outcome rules, or trade-execution behavior.
- Analysis-only; no orders are sent.

This is an experiment, not a claim of improved profitability. Compare against the baseline over a meaningful sample and include skipped-signal shadow outcomes before deciding whether to keep it.
