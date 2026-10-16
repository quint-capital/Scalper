# QUTE V75 Self-Learning Exit Model v1

**Analysis-only / paper outcomes only. No broker orders and no trade execution.** This is a separate experiment based on the structure-led QUTE V75 model. The original signal direction, entry trigger and setup qualification logic in `engine.py` are preserved. This version experiments with TP/SL exit geometry only.

## What it learns

For each eligible signal, the model starts nine independent shadow setups using the same entry and direction but different exit profiles:

- Stop-loss distance: 1.00x, 1.15x, or 1.30x the source structural stop distance. Stops are widened beyond the original structural invalidation, never tightened inside it.
- Take-profit distance: 0.60x, 0.80x, or 1.00x the source structure-led target distance. Targets are never extended beyond the original structural target.
- Each shadow is tracked against subsequent completed M1 candles using the same stop/target outcome rules. If both target and stop are touched in one M1 candle, that outcome is marked ambiguous and excluded from win/loss learning.

The selected policy is chosen using **only already-closed outcomes**. Until every profile has at least 30 resolved outcomes, the selected model uses the original structure-led exit geometry (`SL1.00_TP1.00`) while collecting shadow evidence. After warm-up, it selects the profile with the best conservative mean-R score. When the same pre-outcome context has at least 12 resolved observations per profile, context results are blended with global results. Context uses only information known at setup time: direction, M1 volatility class, and structure-score bucket.

This is constrained online learning, not unrestricted self-modifying code. It does not rewrite `engine.py`, change entries, or change direction logic. Shadow variants allow exit profiles to be compared on the same entry signals, reducing the risk of comparing different entry samples.

## Fresh isolated data files

All journals are dedicated to this model and do not reuse the prior structure-led model's filenames:

- `/app/data/qute_v75_self_learning_analysis_v1.jsonl`
- `/app/data/qute_v75_self_learning_setups_v1.json`
- `/app/data/qute_v75_self_learning_active_v1.json`
- `/app/data/qute_v75_self_learning_state_v1.json`
- `/app/data/qute_v75_self_learning_shadow_setups_v1.json`
- `/app/data/qute_v75_self_learning_shadow_active_v1.json`

Existing market candle history is retained at `/app/data/v75_history.json` for context. The performance and learning history start fresh. Keep the Railway persistent volume mounted at `/app/data` so the journals and learned state survive redeploys.

## Deploy

1. Extract this ZIP and upload the contents of `QUTE-main/` to a **separate GitHub repository or branch** from the original model.
2. Deploy it as a separate Railway service if you want the original and learning model to run side by side. Mount the persistent volume at `/app/data`.
3. Ensure the new service is not configured with old `STRUCTURE_LED_*` journal overrides. This model uses the dedicated `SELF_LEARNING_*` variables instead.
4. Confirm startup logs show the `qute_v75_self_learning_*` paths and `BASELINE_WARMUP`.
5. Watch `[LEARNER SHADOW]`, `[LEARNER UPDATE]`, and `[LEARNER DECISION]` lines. They report alternative exit outcomes, learning statistics and the selected profile.

## Optional configuration

- `LEARNER_MIN_GLOBAL_RESOLVED=30` — minimum resolved outcomes required for each exit profile before selection.
- `LEARNER_MIN_CONTEXT_RESOLVED=12` — minimum per-profile outcomes in a context before contextual blending.
- `LEARNER_COST_POINTS=0` — optional per-trade cost in index-price points used by the learner's score only. Set this only to a defensible estimate for your evaluation; default results are gross of costs.
- `SELF_LEARNING_ANALYSIS_JOURNAL_FILE`, `SELF_LEARNING_SETUP_JOURNAL_FILE`, `SELF_LEARNING_ACTIVE_SETUPS_FILE`, `SELF_LEARNING_STATE_FILE`, `SELF_LEARNING_SHADOW_SETUPS_FILE`, `SELF_LEARNING_SHADOW_ACTIVE_FILE` — dedicated path overrides if required.

## Important limitations

- No profitability is assumed or guaranteed. The first version learns only as fresh live setups close; it does not retroactively replay all bootstrap candles as historical trades.
- Results are M1 OHLC paper estimates, not tick-by-tick fills. Same-candle target/stop collisions are ambiguous. Slippage and costs are not automatically known; configure `LEARNER_COST_POINTS` only if you have a grounded estimate.
- Shadow profiles share the same entry sample, but they are alternative hypothetical exits, not nine independent real trades.
- Let a meaningful number of setups close and compare the selected model against the fixed structure-led baseline before drawing conclusions.
