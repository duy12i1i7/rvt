# Legacy checkpoints — selected under invalid evaluation semantics

**Do not use these checkpoints for any final conclusion.**

Nothing has been deleted; these are retained for provenance only.

## Why they are invalid

These checkpoints were *selected* by a procedure that is itself unsound, so even
re-evaluating them under corrected metrics does not make them usable:

1. **Selection criterion was computed under schema-1 metrics.** Checkpoint ranking
   used `rollout_validation_key` over `success`, `goal_reached`, `collision_free`
   and `form_ok` — all terminal-step quantities at the time. The chosen weights
   are the ones that happened to look best under the broken measure.
2. **Selection ran on the test distribution.** Validation used the test scenario
   generators and test team sizes (N in {8,16,24}), separated from the reported
   episodes only by a seed offset. There was no held-out validation split.
3. **Unequal selection budget.** `rvt_swarm` drew from 30 candidate evaluations,
   `gnn_only` and `instant_cert` from 12.

## Code version

Commit `fab222b` and earlier; anything before branch `fix/benchmark-validity`.

## Required action

Retrain under schema 2 with the split protocol in
`docs/DATA_SPLIT_AND_CHECKPOINT_PROTOCOL.md` and the equalised budgets in
`docs/TRAINING_BUDGET_PROTOCOL.md`. Do not seed new runs from these weights.
