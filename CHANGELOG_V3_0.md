# v3.0 — Adaptive SL/TP Geometry

### Why
v2.9 used the lowest/highest point across the previous 29 M15 candles for the stop. Because TP1 was 1.5R, a wide structural stop automatically produced a very distant target.

### New SL
- Local M1 pivot/invalidation plus M1 ATR buffer.
- M5 pivot/invalidation plus M5 ATR buffer.
- Uses the closer valid local structural invalidation.
- Minimum risk prevents an unrealistically tight stop.
- Maximum risk cap rejects setups whose required stop is too wide.

### New TP
- TP1 seeks nearest opposing M5 pivot above/below entry.
- TP1 must offer at least 1.25R.
- TP1 is capped at 1.75R.
- If no suitable opposing structure exists, TP1 = 1.25R.
- TP2 = 2.0R.
- TP3 = 3.0R.

### Statistics
- Fresh v3.0 setup/active/analysis files.
- TP1-first remains the official outcome.
- Terminal R for TP1 uses the actual dynamic TP1 RR.
