# v3.5 — One-candle entry test (analysis only)

Controlled candidate based on the supplied v3.4 source.

Only strategy change:
- M1 entry confirmation now requires at least 1 counter-direction candle instead of at least 2.
- The directional resumption close beyond the recent three-candle range is still mandatory.
- All other entry filters, direction selection, stop-loss/target geometry, and risk rules are unchanged.

Purpose:
- Test whether the two-candle pullback requirement is unnecessarily suppressing otherwise-confirmed entries.
- This is an experiment, not a claim of profitability. Compare setup frequency and outcomes against the v3.4 baseline with identical conditions and include costs where applicable.
- Analysis only; no trade execution.


Fresh experiment data isolation:
- v3.5 writes analysis logs to `v75_analysis_history_v35.jsonl`.
- v3.5 writes completed setup/outcome history to `v75_setups_v35.json`.
- v3.5 writes active setup records to `v75_active_setups_v35.json`.
- These journal paths are version-specific and ignore legacy journal-path environment overrides, preventing reuse of the old performance journals.
- Historical M1 price history is intentionally preserved; only the performance journals are separated for this experiment.
