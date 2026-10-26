# V3.8 — Reversed strategy repair (analysis-only)

Changes based on the supplied Railway log sample (21 resolved paper setups; 28.6% wins; average MFE 1.17R; planned targets often 1.6R–3.0R):

1. **Emitted-direction confirmation:** after BUY/SELL inversion, require the reversed direction itself to have a completed directional M1 candle, M1 MSS/BOS/displacement, and M5 directional support. Source-direction confirmation is no longer reused as evidence for the opposite trade.
2. **Countertrend protection:** if the emitted direction conflicts with the market regime, allow it only when the emitted direction independently passes the structural-transition test.
3. **Conservative structural stops:** select the farther M1/M5 structural invalidation candidate rather than the closer candidate; the existing ATR stop-width guard can reject excessively wide stops.
4. **Reachability-aware TP1:** cap far structural targets at 1.25R by default, while retaining nearer structural objectives. Configurable with `REV3_MAX_TP1_RR`.
5. **Fresh journal/history namespace:** V3.8 uses REV3 environment variables and separate `qute_v75_improved_reversed_v3_8_*` paths, so its statistics start fresh and do not mix with V2.

No broker execution or order placement was added. This is a testable strategy hypothesis, not a guarantee of profitability. Validate with a fresh chronological paper sample before any live use.
