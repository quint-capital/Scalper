# V3.4 — Single Trade + Fresh Move Protection

- Maximum one active tracked trade at any time.
- Once a trade is created, the current structural move is consumed.
- Changed entry/SL/TP signatures inside the same move cannot create another trade.
- A new trade is permitted only after the market leaves BUY/SELL SETUP state and a fresh setup cycle is detected.
- Previous v3.3 performance/setup journals are not loaded; v3.4 starts its performance counters at zero.
- Existing persistent M1 market history is preserved.
- Trade parameters remain displayed: Entry, SL, TP1, TP2, TP3, risk and RR.
- Analysis only; no execution.
