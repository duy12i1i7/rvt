# RVT Baseline Fairness Contract

Schema: `rvt-baseline-fairness/v1`.

## Deployable Fixed Baselines

1. always COMPACT;
2. always LINE;
3. always KEEP, fixed open-space reference only.

## Deployable Selectors and Methods

4. local geometric COMPACT/LINE selector;
5. direct local learned COMPACT/LINE classifier;
6. recoverability selector without score consensus;
7. recoverability selector with score consensus;
8. full method with frozen base controller;
9. full method with residual action only while H4 remains supported.

## Diagnostic References

10. centralized COMPACT/LINE selector;
11. matched counterfactual rollout oracle;
12. best fixed COMPACT/LINE topology per episode.

All deployable methods use paired layouts/episodes, the frozen controller,
safety projection, transition mechanics and metrics. Comparable learned methods
receive the same encoder scale, data rows, three seeds, 50k steps,
12-configuration tuning cap, validation frequency and checkpoint opportunities.
Communication differences are the stated ablation, not hidden budget changes.

Centralized and rollout references are explicitly non-deployable and may use
offline joint outcomes. KEEP is never an online selector baseline. Inputs,
locality, model capacity, training/checkpoint/tuning budgets, communication,
scenario access and deployability are serialized in the experiment contract.
No heuristic is named after a published method without faithful implementation.
