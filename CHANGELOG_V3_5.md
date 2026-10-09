# V75 v3.5 — Adaptive Risk + Confirmed-Only Trade Capture

## Changes
- Keeps the v3.4 one-trade-at-a-time and fresh-structural-move lock.
- Adds an adaptive structural-stop risk gate: strong setups (max of structure/trigger/continuation/transition score >= 80) can use a wider cap than ordinary setups.
- Ordinary setups retain the tighter risk cap.
- Removes trade-parameter generation from `ARMED — WAIT FOR PULLBACK`; trade parameters are now only produced for confirmed `BUY SETUP` / `SELL SETUP` states.
- Fresh v3.5 analysis/setup/active journals isolate performance from v3.4 and earlier versions.
- Existing persistent M1 market history remains unchanged.
- Analysis only; no trade execution.

## Research intent
The v3.4 log showed 16 closed setups, 6 wins and 10 losses, while the engine also repeatedly reached `NO TRADE — RISK TOO WIDE`. v3.5 addresses that specific opportunity bottleneck without simply disabling the risk gate.

This is a research enhancement, not a claim of profitability. The new version must be evaluated on fresh out-of-sample live data.
