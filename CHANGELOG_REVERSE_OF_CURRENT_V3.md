# Reverse-of-Current V3 — paper-only experiment

- Keeps the existing analysis/entry detection engine unchanged.
- When the current strategy emits BUY SETUP, this experiment records SELL; SELL SETUP records BUY.
- The current setup TP1 price becomes the inverse stop-loss, and the current setup SL price becomes the inverse take-profit. Prices are swapped exactly; no target widening or RR adjustment is applied.
- Uses separate V3 JSON/JSONL journals so its performance does not mix with prior experiments.
- Continues to use the existing Deriv R_75 live tick feed and one-open-paper-setup / one-setup-per-move behavior.
- Paper-only: no broker orders or MT5 execution.
- Startup log still labels the existing one-candle OHLC outcome model; same-candle stop/target hits remain ambiguous.
