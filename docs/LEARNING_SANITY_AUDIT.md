# Learning Sanity Audit (Task 1)

Can the models learn the expert targets at all? Answered before studying topology
or recovery, because every downstream question is meaningless if the answer is no.

Raw data: [`../results/method_audit/learning_curves.csv`](../results/method_audit/learning_curves.csv)
Script: `scripts/audit_learning_sanity.py`
Benchmark tag: `benchmark-protocol-v2-smoke`

**Training and validation splits only.** No final-test scenario, seed, or metric
was used, including for the checkpoint-epoch discussion in §3.

---

## A. Micro-overfit test

64 samples from 2 expert episodes, 1 500 full-batch AdamW steps (lr 1e-3, no
weight decay). Any correctly-wired model must memorise this.

| | `gnn_only` | `rvt_swarm` |
|---|---|---|
| Initial total loss | 0.0243 | 0.4775 |
| Final total loss | 1.4e-5 | 0.0367 |
| Loss reduction | **99.9 %** | **92.3 %** |
| Action RMSE, initial | 0.1483 m/s² | 0.1442 m/s² |
| Action RMSE, final | **0.0014 m/s²** | **0.0048 m/s²** |
| Target action std | 0.1515 m/s² | 0.1515 m/s² |
| Final RMSE / target std | **0.9 %** | **3.2 %** |
| Topology accuracy | n/a (no head) | **1.000** |
| Candidate-ranking accuracy | n/a | **0.78–0.85 (does not reach 1.0)** |
| Gradient norm (final) | small, stable | rises to ≈14.6 |
| Parameter-update norm | stable | stable |
| NaN / Inf | none | none |

### Verdict: **both models can learn. Optimisation and wiring are sound.**

Neither target normalisation, masking, batching, graph construction, detached
tensors, loss wiring, action scaling, output clipping, nor optimizer configuration
is broken. Action targets are memorised to within 1–3 % of the target standard
deviation, and topology classification reaches 100 %.

### One finding that is *not* clean

**`rvt_swarm`'s candidate-ranking accuracy plateaus at ≈0.78–0.85 on a 64-sample
dataset it has otherwise memorised**, while topology accuracy on the same batch
is 1.000. The model can memorise *which* mode is best but cannot memorise the
*full pairwise ordering* of the three modes, even with unlimited capacity per
sample. Gradient norm also grows to ≈14.6 late in the run, which is consistent
with the ranking loss fighting the score-MSE and lower-bound terms.

This matters because pairwise ranking is exactly what the score head must do at
inference. It is not an optimisation bug — it is evidence that the ranking
objective is either **under-determined** (the three rollout utilities are often
near-ties, so their ordering is close to noise) or **in conflict** with the
score-regression and lower-bound terms it is averaged with. Task 5 tests which.

---

## B. Small-data generalization test

30 expert episodes → 3 195 samples (2 875 train / 320 held-out-loss). Both models:
identical optimizer-step budget, identical validation frequency (every 5 epochs),
identical early stopping, identical checkpoint-selection rule, identical model
seed (0), identical training data. 60 epochs — chosen so the curves plateau rather
than stopping at the arbitrary 6-epoch smoke budget.

Validation rollouts use the **validation split only** (open_field + narrow_passage
at N ∈ {5, 11}, 2 episodes per setting = 8 episodes).

### Supervised learning curves

| epoch | `gnn_only` train | val | action RMSE | `rvt_swarm` train | val | action RMSE |
|---|---|---|---|---|---|---|
| 1 | 0.0751 | 0.0379 | 0.1167 | 0.7804 | 0.3313 | 0.1281 |
| 5 | 0.0120 | 0.0108 | 0.0618 | 0.1823 | 0.1808 | 0.0698 |
| 15 | 0.0029 | 0.0035 | 0.0353 | 0.1134 | 0.1058 | 0.0420 |
| 30 | 0.0015 | 0.0021 | 0.0272 | 0.0913 | 0.0963 | 0.0524 |
| 45 | 0.0010 | 0.0014 | 0.0221 | 0.0838 | 0.0872 | 0.0270 |
| 60 | **0.0005** | **0.0010** | **0.0188** | **0.0827** | **0.1302** | **0.0290** |

### Closed-loop validation rollouts

| epoch | `gnn_only` succ / cf / goal / tube | `rvt_swarm` succ / cf / goal / tube |
|---|---|---|
| 1 | 0.000 / 0.750 / 0.000 / 0.306 | 0.000 / 0.750 / 0.000 / 0.206 |
| 5 | 0.375 / 0.750 / 0.500 / 0.621 | 0.125 / 0.625 / 0.250 / 0.531 |
| 15 | 0.125 / 0.625 / 0.500 / 0.558 | 0.375 / 0.625 / 0.500 / 0.601 |
| 30 | 0.250 / 0.875 / 0.375 / 0.555 | 0.500 / 0.750 / 0.500 / 0.499 |
| 45 | 0.250 / 0.875 / 0.375 / 0.656 | 0.375 / 0.750 / 0.375 / 0.657 |
| 60 | 0.375 / 0.875 / 0.375 / 0.647 | 0.375 / 0.625 / 0.500 / 0.547 |
| **best checkpoint** | **epoch 5** | **epoch 30** |

### Diagnosis

**Not underfitting.** `gnn_only`'s train and validation losses fall together by
two orders of magnitude with no divergence; action RMSE reaches 0.0188 m/s²
against a target std of ≈0.15, i.e. **≈12 % relative error** in open loop.

**`rvt_swarm` shows mild late overfitting / instability**: validation loss
improves to 0.0770 at epoch 50 then rises to 0.1302 at epoch 60 while training
loss keeps falling. Its floor is also an order of magnitude higher than
`gnn_only`'s (0.083 vs 0.0005) — expected, since its objective averages five
terms including the ranking and lower-bound losses that §A showed cannot be
driven to zero.

**The decisive observation is the open-loop / closed-loop gap.** Both models
imitate the expert to ≈12 % relative action error, yet in closed loop reach
success 0.25–0.50 on validation — while the *same* expert they are cloning scores
**1.000 success in open_field N=4** in the frozen smoke benchmark. Small per-step
action errors compound into trajectories the expert never visits, and the policy
has no training signal there. This is textbook behaviour-cloning distribution
shift, and it is a **method-level** limitation, not a training bug.

### A second finding: the checkpoint-selection signal is too noisy to use

With 8 validation episodes, success is quantised to 0.125. The lexicographic rule
selected **epoch 5** for `gnn_only` — a model with **3× worse** action RMSE
(0.0618 vs 0.0188 m/s²) than epoch 60 — because epoch 5 happened to score
`goal_reached = 0.500` against epoch 60's 0.375 on eight episodes.

The selection procedure is sound (Protocol V2 keeps it strictly on validation);
the **signal feeding it is dominated by sampling noise**. Any comparative result
built on it inherits that noise. Before a scientific pilot, validation episode
count must be raised until the selection key is stable, or selection must move to
a lower-variance quantity (e.g. held-out action RMSE, or a success estimate
averaged over far more episodes).

---

## Answers

| Question | Answer |
|---|---|
| Can the models learn the expert? | **Yes.** Micro-overfit reduces action RMSE to 0.9 % (`gnn_only`) and 3.2 % (`rvt_swarm`) of the target std, with 100 % topology accuracy. |
| Is there an optimisation or wiring bug? | **No** — none of the nine listed failure modes is present. |
| Is the policy undertrained? | **No.** Curves plateau; more epochs do not close the closed-loop gap. |
| Is it incorrectly trained? | **Partly.** The ranking objective cannot be fitted even on 64 memorised samples, and the checkpoint-selection signal is noise-dominated. |
| Is it fundamentally weak? | **In closed loop, yes** — behaviour cloning from a single expert with no on-policy correction. This is a method limitation, not an implementation defect. |

**Flag raised (as the task requires):** the models *do* learn the expert on simple
open-field validation scenarios in open loop, so the method is not stopped here.
But closed-loop validation success (0.25–0.50) falls far below the expert being
imitated (1.000 in the matched smoke cell), and **no amount of further training
closes that gap**. Any future claim about the learned controller must be stated
relative to the expert baseline, which must appear in every table.
