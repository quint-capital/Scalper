# Self-Learning Exit Model v1

- Forked from the structure-led exit model; original entry and direction logic remains unchanged.
- Added nine parallel shadow exit profiles using stop multipliers 1.00/1.15/1.30 and target multipliers 0.60/0.80/1.00.
- Added a persistent contextual learner that scores already-closed outcomes with conservative mean-R estimates and chooses a profile walk-forward.
- Uses the baseline structural exit profile until at least 30 resolved outcomes exist for every profile; contextual results blend in after 12 resolved outcomes per profile in the context bucket.
- Ambiguous same-candle outcomes are excluded from win/loss scoring.
- Added a dedicated fresh journal namespace; previous structure-led history is not loaded into this model's trade history or learning state.
- Analysis only; no broker execution. No claim of improved profitability until independently observed results support it.
