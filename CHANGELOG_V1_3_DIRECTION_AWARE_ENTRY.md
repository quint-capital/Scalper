# Quint Capital V75 Scalper v1.3 — Direction-Aware Entry Experiment

Analysis-only. No trade execution.

## Changes
- Transition candidate is calculated for both BULLISH and BEARISH, then the higher-scoring candidate is selected.
- Entry acceptance requires a completed M1 pullback/resumption sequence: at least two counter-direction candles among the previous five, followed by a close beyond the recent three-candle range in the candidate direction.
- Adds `entry_gate` diagnostics to the analysis result.

## Explicitly unchanged
- `_setup()` stop-loss logic and risk caps.
- TP1/TP2/TP3 geometry and skip rules.
- Outcome journaling and trade execution behavior (still analysis-only).

## Testing note
The filter may reduce setup frequency. It has not been proven profitable. Compare completed outcomes and also track skipped candidate outcomes before adopting it as the main version.
