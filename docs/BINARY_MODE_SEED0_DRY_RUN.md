# Binary Mode Pilot — Stage 1 Seed-0 Engineering Dry Run

Results: `results/binary_mode_pilot/dry_run_seed0/`
Scripts: `scripts/train_binary_pilot.py`, `rvt_swarm/binary_pilot.py`
**Implementation-validity check only. Not a model-selection experiment.**

Three methods, model seed 0, equal budgets: 24 epochs · batch 32 · AdamW lr 3e-4,
wd 1e-5 · validation every 4 epochs (6 calls) · patience 6 · checkpoint pool 6 ·
**zero method-specific hyperparameter tuning** · 457 train / 302 validation states.

---

## 1. Verification checklist

| # | Check | Result |
|---|---|---|
| 1 | No final-test layout, hash, seed, or result loaded | **PASS** — `build_dataset` reads `build_layouts("train"/"val")` only; no `test` call path exists in the training script |
| 2 | Exactly one writer per checkpoint directory | **PASS** — `CheckpointWriterLock` held for the whole run; token written into every checkpoint |
| 3 | Identical training/validation state IDs across methods | **PASS** — all three consume the same `PilotSample` list built from the same label file |
| 4 | No NaN/Inf in losses, gradients, parameters, probabilities, actions, metrics | **PASS** — all finite across all 72 epoch-records |
| 5 | Recovery probabilities strictly in [0,1] | **PASS** — sigmoid outputs; asserted by `test_recovery_outputs_are_probabilities` |
| 6 | BCE decreases from initialization | **PASS** — 0.678 → 0.472 |
| 7 | Gradients reach all five components | **PASS** — trunk 0.403; heads `base_action_head`, `mode_action_head`, `recovery_head` all non-zero |
| 8 | Matched-capacity comparison retained | **PASS** — both mode-conditioned models are **401,926** parameters |
| 9 | Selection uses only the frozen hierarchy | **PASS** — `selection_key` = (−Brier, ranking accuracy, constrained success) |
| 10 | Validation reported per N and per family | **PASS** — `stratified_metrics` emits `all`, `N=4`, `N=6`, and all four families |
| — | **11. Reported metrics are meaningful** | **FAIL** — see §3 |
| — | **12. Closed-loop criterion is informative** | **FAIL** — see §4 |

## 2. Training behaviour

**`rvt_binary_recovery`** — the recovery head learns cleanly:

| epoch | total | Brier | NLL | AUROC | action RMSE |
|---|---|---|---|---|---|
| 4 | 0.678 | 0.204 | 0.596 | 0.713 | 0.225 |
| 12 | 0.541 | 0.163 | 0.504 | 0.829 | 0.169 |
| 24 | **0.472** | **0.142** | **0.438** | **0.861** | 0.150 |

**`direct_keep_line_classifier`** — Brier 0.432 → 0.414, AUROC ≈ 0.51 (chance).
**`topology_agnostic_gnn`** — action-only, as designed.

The recovery head reaching **validation AUROC 0.861** on geometrically disjoint
layouts is a genuinely encouraging signal. It is *not* a result — this is one
seed, seen during an engineering check — but it shows the learning path works.

## 3. DEFECT 1 — `top1_mode_accuracy` is degenerate under label ties

`top1 = mean(argmax(probs) == argmax(labels))`. The label vector is
`[keep_label, line_label]`, so `argmax` resolves to **keep** whenever both modes
succeed *and* whenever both fail. Only `line_only` states (14.6 % of validation)
put the argmax on line.

**Measured: a constant "always predict keep" predictor scores
`top1_mode_accuracy = 0.854`.**

That is exactly what `direct_keep_line_classifier` scored (0.854) — it learned the
majority class, and the metric rewarded it. `rvt_binary_recovery` scored 0.457
because it predicts probabilities and its argmax selects line more often.

**Read naively, this metric says the degenerate classifier is nearly twice as good
as the model that actually learned the signal.** It is uninformative at best and
actively misleading at worst.

Selection was unaffected — the frozen hierarchy uses Brier → pairwise ranking →
closed-loop, not top-1 — but Stage 6 requires top-1 as a headline mode-selection
metric, so it must be repaired before any reported run.

**Repair:** restrict top-1 to states where the modes actually disagree, and report
the always-keep baseline alongside it so degeneracy is visible. `pairwise_ranking_accuracy`
(already restricted to disagreeing states) is unaffected and remains the primary
ranking metric.

## 4. DEFECT 2 — closed-loop validation is uninformative at this data scale

**Constrained closed-loop success was exactly 0.000 for all three methods at every
validation call.**

Run on the *same* validation episodes:

| controller | constrained closed-loop success |
|---|---|
| expert, mode pinned to **keep** | **0.450** |
| expert, mode pinned to **line** | **1.000** |
| all three learned methods | **0.000** |

So the zeros are not an episode-setup problem — the episodes are solvable, and the
keep/line gap on them is **0.550 absolute**, the largest headroom measured anywhere
in this project. The learned methods cannot execute *either* mode.

The cause is action-head starvation. The pilot dataset has **457 training states**,
because label generation sampled every 12th step of 3 episodes per (layout, N) —
sized for the *recovery* head, which needs an expensive V2 rollout per state. The
*action* head needs no labels at all, only expert targets, and 457 samples leaves
it at action RMSE 0.150 (normalised) against a target standard deviation of ≈0.15
— i.e. barely better than predicting zero. For comparison, the learning-sanity
audit reached 0.019 with 3 195 samples.

**Consequence if unrepaired:** gate G2 compares closed-loop Task-Recovery rate
against `always_keep`. With every learned method at 0.000, G2 cannot discriminate,
and the tertiary selection criterion is a constant that never breaks a tie. Nine
training runs would produce a pilot whose closed-loop arm is structurally dead.

**Repair:** decouple the two supervisions, which have different data requirements.
The recovery head keeps the 759 V2-labelled states (expensive, unchanged). The
action head trains on a much larger set of expert action targets sampled from the
same **train layouts** at a fine stride — cheap, since it needs no rollouts. Both
draw from the same layout split; no test data is involved; no reweighting is
introduced.

## 5. Verdict

> ### **A — Invalid implementation. Repair and restart all training.**

Not B. Both defects are implementation faults in the experimental apparatus, not
model quality:

- Defect 1 would make the headline mode-selection metric reward a degenerate
  classifier.
- Defect 2 would make the closed-loop half of the pilot — and gate G2 — incapable
  of measuring anything.

Neither is a reason to stop the *pilot*; both are reasons to fix the harness before
spending nine training runs on it. This is precisely what Stage 1 exists to catch.

**Per the Stage 1 rule, no dry-run checkpoint will be reused.**
`checkpoints/binary_mode_pilot_dryrun/` is deleted; the Stage 3 runs will start
from scratch after the repair.

## 6. Repair plan (no protocol drift)

| Change | Touches a frozen quantity? |
|---|---|
| Restrict `top1_mode_accuracy` to disagreeing states; report always-keep baseline | **No** — reporting only; selection hierarchy unchanged |
| Add expert-action samples from **train layouts** for the action head | **No** — architecture, losses, label definition, validation layouts, selection hierarchy and decision thresholds all unchanged |

Explicitly **not** changed: BCE-only loss · no class weighting, focal loss,
oversampling, outcome balancing, family weighting, or ranking term · no split ·
no switching · no uncertainty head · no threshold tuning · the Recovery Event V2
label definition · the validation layout set · the gates G1–G4.

The implementation is **not** frozen yet — Stage 2 follows a verdict B — so this
repair happens before the freeze, which is the correct ordering.

## 7. What the dry run did establish

- Provenance, writer-exclusivity, leakage isolation, numerical health, gradient
  flow, and matched capacity are all sound.
- The recovery head learns: validation AUROC 0.713 → **0.861** across 24 epochs.
- The keep/line headroom is real and large on the constrained validation
  layouts — **expert-line 1.000 vs expert-keep 0.450**.

The hypothesis remains testable. The harness needs two fixes first.
