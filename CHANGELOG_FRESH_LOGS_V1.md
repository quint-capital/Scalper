# Fresh Logs V1

- Starts a clean paper-performance journal using new v1-specific analysis, setup, and active-setup filenames.
- Previous QUTE/inverse/baseline outcome records are not loaded into the new performance counters.
- Preserves the existing market candle-history file so the bot can still build its timeframe context efficiently.
- Keeps the double-reversed baseline logic: original BUY/SELL direction restored, original SL/TP1 geometry restored, TP1 only, analysis-only with no broker orders.
- For a truly clean journal, do not override the three journal path environment variables with old filenames.
