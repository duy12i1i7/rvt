# Dual Supervision Data Protocol (Repairs 2–5)

**Predeclared before any new data generation or retraining.**
Implementation: `rvt_swarm/binary_pilot.py` · Statistics:
`results/binary_mode_pilot/action_dataset_statistics.csv`

## 1. Why two datasets

Action supervision and recovery supervision have different costs and different
data requirements, and conflating them starved the action head:

| | recovery supervision | action supervision |
|---|---|---|
| Needs | a full Recovery Event V2 rollout per (state, mode) | an expert action query |
| Cost | ~120 simulator steps × 2 modes × 4 rollouts | one function call |
| v1 consequence | 759 states — appropriate | **457 training states — starved** |

At 457 states the action head reached RMSE 0.150 against a target standard
deviation of ≈0.15 — indistinguishable from predicting zero — and every learned
method scored **0.000** closed-loop while the expert scored 0.450 (keep) and
1.000 (line) on the same episodes.

## 2. A — Dense action dataset (new)

**Predeclared before generation:**

| Parameter | Value |
|---|---|
| Layouts | `build_layouts("train")` restricted to the four pilot families |
| Layout IDs | `train_line_corridor_{001,002,003}`, `train_keep_line_keep_{001,002}`, `train_keep_open_{001,002}`, `train_ambiguous_{001,002}` |
| Team sizes | 4, 6 |
| Trajectories per (layout, N) | 3 (the same episode seeds as the label set) |
| Timestep stride | **2** |
| Targets | keep-conditioned **and** line-conditioned expert actions at every sampled step |
| Recovery rollouts | **none** |
| Outcome-based sampling | **none** |
| Expected sample range | 2 500 – 4 000 states |

Validation uses the same construction on `build_layouts("val")`.
**No final-test layout is loaded.**

The identical dense dataset — same state IDs, same order — is used by
`topology_agnostic_gnn`, `direct_keep_line_classifier`, and
`rvt_binary_recovery`.

## 3. B — Sparse recovery dataset (unchanged)

The existing **759-state** Recovery Event V2 dataset
(`results/binary_mode_pilot/task_recovery_labels.csv`) is used **only** for:

- BCE recovery supervision (`rvt_binary_recovery`);
- decisive-state classification supervision (`direct_keep_line_classifier`);
- recovery and mode-selection validation metrics.

**Labels are not regenerated to improve balance.** No reweighting of any kind.

## 4. Fixed training schedule (Repair 4)

Predeclared, identical for all three methods:

```
for step in range(TOTAL_STEPS):
    action_batch   = next(dense_action_loader)          # same IDs, same order, all methods
    recovery_batch = next(recovery_loader)              # only if the method needs it
    loss = L_action  [+ λ_bce · L_task_recovery  |  + λ_cls · L_decisive_classifier]
    optimizer.step()
```

| Method | Loss |
|---|---|
| `topology_agnostic_gnn` | `L_action` |
| `direct_keep_line_classifier` | `L_action + λ_cls · L_decisive_classifier` |
| `rvt_binary_recovery` | `L_action + λ_bce · L_task_recovery` |

`λ_bce = λ_cls = 1.0`, declared here before training.

**Every method takes the same number of optimizer steps over the same dense
action batches.** No method receives extra low-level action updates because it
carries an additional head — the recovery/classifier terms ride on the same
steps, they do not add steps.

## 5. Masked classifier target (Repair 2)

`direct_keep_line_classifier` previously received `keep` as the target for
both-succeed and both-fail states — an arbitrary tie-break that taught it the
majority class.

Now:

- cross-entropy applies **only to decisive states**;
- `keep_only` → target keep, `line_only` → target line;
- both-succeed and both-fail are **masked out of the classifier loss**;
- those states are **still used for action supervision** — they are masked from
  one loss term, not discarded;
- a minibatch containing no decisive state contributes **exactly zero** classifier
  loss, with no division by zero and no NaN.

No class balancing, no outcome oversampling.

## 6. Selector-only vs end-to-end evaluation (Repair 5)

Two configurations, **never combined**:

| | Selector | Executor |
|---|---|---|
| **A — selector-only** | learned predictor / classifier / oracle | **trusted expert controller** |
| **B — end-to-end** | learned predictor | **learned action head** |

A measures whether the *mode decision* is useful, free of imitation-policy
failure. B measures the deployable system. Reported quantities:
`selector_only_task_recovery`, `end_to_end_task_recovery`, and the **gap**.

Interpretation, fixed in advance:

| Observation | Conclusion |
|---|---|
| A succeeds, B fails | low-level action control is the limitation |
| A and B both fail | the selector or the labels remain inadequate |
| A and B both succeed | the mechanism is ready for multi-seed evaluation |

Selector-only arm includes: always-keep, always-line, direct classifier, recovery
predictor, and the mode oracle — all with expert execution.

## 7. Action-learning validation (Repair 6)

Before any closed-loop validation, report: dense sample count · action-target
standard deviation · train and validation action RMSE · **normalised RMSE
(RMSE / target std)** · split by keep vs line · split by N = 4 vs N = 6 · split by
family. Plus a micro-overfit test asserting the action heads can memorise a small
fixed batch of the new dense dataset.

The dry run does not require publication-level closed-loop performance, but the
learned controllers must demonstrate non-trivial execution of **both** keep and
line.

## 8. Unchanged

Recovery Event V2 · gates G1–G4 · checkpoint-selection hierarchy · BCE-only
recovery loss · no class weights, focal loss, oversampling, outcome balancing,
family weighting, pairwise ranking, or post-hoc threshold tuning · no split ·
no switching · no uncertainty head · validation layout set · **no final-test
access**.
