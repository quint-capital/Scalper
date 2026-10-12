# v3.7 — More responsive entries (analysis-only)

- Correct-side V75 system only; no inverse/opposite signal logic added.
- Adds a continuation-only fast confirmation route: directional completed M1 candle plus M1 BOS/MSS or displacement. It does not require the usual pullback sequence for this pathway.
- Keeps extension, exhaustion, adverse microstructure, structural stop and risk-cap protections.
- Lowers the default minimum structural TP1 room from 0.75R to 0.40R. If no confirmed opposing M5 pivot is available, uses a clearly labelled 0.50R fallback target; all outcomes remain simulated/journaled, with no orders placed.
- Retains the existing one-active-setup and one-setup-per-structural-move safeguards.
- These are hypotheses to test, not claims of profitability. Compare at least 20 closed setups and monitor terminal R, drawdown, win rate and missed signals against v3.6.
