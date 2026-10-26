# Improved Reversed-Signal V1

- Audited and corrected misleading labels: source direction is generated, then emitted BUY/SELL is reversed.
- Added market regime classification and range/transition no-trade gate.
- Added emitted-direction M1 close + M1 structure + M5 support confirmation.
- Added post-loss cooldown and temporary loss-streak brake.
- Added final direction-aware SL/TP geometry, M5 ATR stop-width and minimum structural RR checks.
- Added explicit regime/confirmation diagnostics to setup records.
- Renamed history, journal, active setup, and storage marker paths to a unique improved-reversed V1 namespace.
- Kept analysis-only; no execution code added.
