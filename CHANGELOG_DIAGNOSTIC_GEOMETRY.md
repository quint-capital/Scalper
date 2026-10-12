# Geometry rejection diagnostics

- No entry, stop, target, score, or risk threshold has been changed.
- When a candidate is rejected by the existing scalp geometry gate, the `STATE` line now reports the exact rejection class and reason, plus entry/SL/risk.
- For `SCALP TARGET TOO CLOSE`, the log also reports available target room, required room, and the nearest M5 opposing pivot.
- This is a diagnostics-only change for the analysis/paper-outcome system. It does not execute trades.
