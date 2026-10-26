# V3.10 — M15/M5/M1-only focus

- M15 is the short-term context timeframe.
- M5 validates setups.
- M1 provides entry timing.
- H4, H1 and M30 are no longer constructed by the live frame builder or used as direction vetoes.
- Preserves reversed BUY/SELL direction behavior, existing geometry checks, analysis-only mode, and separate fresh-history/journal configuration.
- Historical tick backtester now constructs/replays only M15/M5/M1 candles.

This change increases the opportunity set by removing higher-timeframe vetoes, but does not establish profitability. Run the seven-day replay and compare results before relying on it.
