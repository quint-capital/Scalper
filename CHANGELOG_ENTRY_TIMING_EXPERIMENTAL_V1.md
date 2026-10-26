# Entry-Timing Experimental v1

- Preserved the existing direction-selection, trigger-generation and setup geometry logic.
- Added a pre-acceptance timing filter for persistent M15/M5 counter-direction momentum.
- Added a stronger M15/M5 trend plus M5/M1 momentum conflict guard.
- Added an M5 extension guard for continuation entries.
- Added a compressed-M5 guard requiring M1 structure/displacement evidence.
- Filter decisions and reasons are written to the analysis journal.
- Isolated history, active setups, setup history, analysis journal and volume marker from the original deployment.
- Analysis-only; no execution functionality added.
- Experimental thresholds are not validated; compare against the unchanged original over the same market period.
