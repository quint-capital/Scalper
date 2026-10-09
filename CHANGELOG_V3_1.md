# V75 v3.1 — Opportunity Expansion

## Goal
Increase the number of valid trades without simply weakening the existing reversal logic.

## Added setup paths
1. REVERSAL — existing high-quality sweep/MSS/displacement path remains intact.
2. PULLBACK CONTINUATION — H1/M30 directional context, M15/M5 participation, M1 resumes the established direction after counter-direction pressure.
3. MOMENTUM CONTINUATION — established H1/M30 direction with lower-timeframe continuation trigger, provided the move is not excessively extended.

## Design rules
- H1 is the primary directional filter; H4 is context rather than an entry requirement.
- Continuation setups do not require a liquidity sweep or FVG by themselves.
- Existing exhaustion and late-entry protections remain active.
- Existing adaptive M1/M5 SL and TP1/TP2/TP3 geometry remains unchanged.
- New setup type and continuation score are journaled separately.
- Fresh v3.1 journal filenames prevent mixing results with v3.0.
- Alert cooldown defaults to 5 minutes and alerts can fire on a genuinely new setup signature.

## Safety
Analysis only. No trade execution.
