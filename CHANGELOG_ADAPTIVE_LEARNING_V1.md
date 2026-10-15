# Adaptive Learning V1

- Forked from the supplied QUTE V75 package into a separate service.
- Preserved the supplied engine and its entry / SL / TP1 calculations.
- Isolated all default history, setup, active, analysis, shadow, and model paths.
- Added a persistent online context learner with cautious warm-up and multi-bucket negative-evidence gating.
- Added a shadow-outcome journal so filtered candidates still contribute outcome feedback.
- Added explicit learner decisions, model summaries, and a 100-resolved-active-setup milestone.
- Analysis-only; no broker order or MT5 execution functionality added.
