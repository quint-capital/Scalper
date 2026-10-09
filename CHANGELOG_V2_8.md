# Quint Capital V75 Engine v2.8.1

## Critical persistence fix
- v2.8 now uses isolated setup and active-setup journal files by default.
- Existing `/app/data/v75_setups.json` and `/app/data/v75_active_setups.json` are left untouched.
- v2.8 statistics therefore start from zero for the corrected TP1-first methodology instead of inheriting old v2.7 results.

## Outcome logic
- TP1 (+1.5R) is the official research WIN.
- SL (-1R) first is LOSS.
- TP1 and SL in the same M1 candle is AMBIGUOUS.
- TP2/TP3 remain milestones only.

## MSS / confirmation
- Corrected MSS requires sweep/rejection followed by structure break.
- Confirmation types are deduplicated.
