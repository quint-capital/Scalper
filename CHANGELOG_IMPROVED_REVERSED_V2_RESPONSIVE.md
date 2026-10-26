# Quint Capital V75 Improved Reversed V2 Responsive

## Purpose
A separate analysis-only experiment derived from the supplied `Quint-Capital` ZIP. It preserves the original source-direction signal-generation thresholds and intentionally emits the opposite BUY/SELL direction. It does not place or execute trades.

## Main change
V1 applied source-direction timing as a hard gate, then applied timing again after reversing direction, and finally required a second M1/M5 confirmation for the inverse direction. These overlapping gates could reject nearly every candidate because they demand confirmation for both opposing directions on the same decision snapshot.

V2 keeps the source strategy's original trigger/entry-confirmation requirements, records source timing as a diagnostic rather than a hard veto, and does not require a contradictory second confirmation in the reversed direction. The reversed setup must still pass:
- market-regime gate (range/transition setups remain blocked),
- directionally valid structural SL/TP geometry,
- maximum stop distance relative to M5 ATR,
- minimum TP1 reward/risk,
- post-loss cooldown and consecutive-loss brake,
- one active tracked setup and one setup per structural move.

## Isolation
All default history, analysis journal, active setup, setup history and storage marker paths use `qute_v75_improved_reversed_v2_responsive*`. The V1 files and journal paths are not overwritten. The version uses separate environment-variable names for its own data paths and risk controls.

## Validation performed
- Python compilation check for all project `.py` files.
- Unit tests: `tests/test_improved_filters.py` (4 tests passed).
- ZIP integrity check.

## Important interpretation
This change should increase the number of qualifying inverse setups by removing the contradictory duplicate gates. It does not guarantee more trades in every market or better profitability. Keep it deployed separately from V1 and compare a meaningful sample of resolved outcomes before deciding which version performs better.
