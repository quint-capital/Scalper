# Quint Capital V75 Adaptive — Independent Paper Learning System

**Analysis-only. No broker orders. No MT5.** This is a separate experimental service based on the supplied QUTE V75 engine. It does not edit or share the original service's journals by default. Keep the original running unchanged.

## What this version does

- Starts from the existing entry logic and setup geometry; it does not rewrite the engine's entry, stop-loss, or TP1 formulas.
- Creates an independent actual-paper journal and a separate **shadow journal** for every eligible setup candidate.
- The shadow journal tracks outcomes even when the learner filters a candidate, so the model can learn from accepted and rejected candidates instead of only seeing its own accepted trades.
- Learns online from realized R across multiple context groups: direction, structure-score band, trigger-score band, confirmations, trend alignment, M1/M5 agreement, exhaustion, and M15/M1 location.
- Passes all candidates through during warm-up. Default warm-up is 30 resolved shadow candidates. After warm-up, it filters a candidate only when at least two sufficiently sampled context buckets show a cautious upper estimate below -0.05R. This is a conservative rule, not a guarantee of better performance.
- Never changes entry, SL, TP1, direction calculation, or the underlying engine rules automatically. Adaptation is limited to an evidence-based setup acceptance filter.
- Logs learner decisions and model summaries. The original service is not connected to this model.
- Emits a milestone when 100 resolved active paper setups have been recorded. Review the comparison only after an adequate sample; this package does not automatically claim it is better.

## Deploy as a separate Railway service

1. Create a **new GitHub repository** for this folder, or a new branch/repository that is deployed as a different Railway service. Do not overwrite the original repository/service.
2. Upload the contents of this folder to the new repository. `main.py` is the entry point used by the existing deployment setup.
3. Create/attach a persistent Railway volume mounted at `/app/data` for the new service. Do not point the new service's environment variables at the original service's files.
4. Set `DERIV_SYMBOL=R_75` if needed. Keep the WebSocket endpoint configuration from the original working package.
5. Deploy and verify logs for `[DATA] Live stream active`, `[HEARTBEAT]` (where emitted by the existing data client), `[LEARN] Model loaded`, and the shadow/actual journals being written.

## Isolated default files

- `/app/data/qute_adaptive_v75_history.json`
- `/app/data/qute_adaptive_analysis_v1.jsonl`
- `/app/data/qute_adaptive_setups_v1.json`
- `/app/data/qute_adaptive_active_v1.json`
- `/app/data/qute_adaptive_shadow_active_v1.json`
- `/app/data/qute_adaptive_shadow_history_v1.json`
- `/app/data/qute_adaptive_model_v1.json`

All can be overridden through environment variables in `config.py`. The filenames are deliberately distinct from the original system's defaults.

## Learning safeguards and limitations

- The learner only uses resolved TP1/SL shadow outcomes. Ambiguous same-M1-candle SL/TP1 cases are excluded from learning.
- The learner uses a cautious, interpretable context-bucket model, not a black-box promise of profit. Sparse groups do not trigger filtering.
- Candidate shadow outcomes use M1 OHLC, so same-candle collisions remain ambiguous and execution costs/slippage are not modeled.
- The initial strategy's existing rules and geometry are inherited as a starting point; no result is guaranteed. Adaptive filtering may improve, worsen, or leave performance unchanged.
- Do not compare systems on win rate alone. At 100 resolved active setups, compare net points, realized R, profit factor, drawdown, average reward/loss, trade count, ambiguous outcomes, and the market period covered.
- This package does not place orders, access a trading account, or connect to MT5.

## Recommended observation plan

Let the service collect its own data. Do not tune thresholds in response to every short losing streak. Keep the learner's JSON model and journals on persistent storage. Once the new system has 100 resolved active paper setups, export both systems' summaries and compare the same period where possible. If the adaptive version underperforms, disable the learner filter with a controlled code/config change rather than modifying the original service.
