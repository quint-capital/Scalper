# Fresh Structure-Led Journal v1

- Added a dedicated journal namespace for the structure-led exit model.
- New setup, active-setup, and analysis files are separate from all legacy journal paths.
- Legacy generic journal environment variables are not used, preventing Railway variables from silently reconnecting this version to old trade history.
- Setup IDs and strategy labels identify `QUTE_V75_STRUCTURE_LED_EXITS_V1`.
- Existing market candle history is preserved; existing trade outcomes are not imported.
- Analysis-only; no broker orders or execution functionality added.
