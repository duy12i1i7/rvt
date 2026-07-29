# Legacy recovery labels (V1) — INVALID for scientific conclusions

**Do not use anything in this directory for training, calibration, model
selection, threshold choice, or any publication conclusion.**

Nothing was deleted. These are copies, retained for provenance and for
before/after comparison against Recovery Event V2.

## What the V1 event was

A rollout was labelled *recovered* if, over a horizon of **H = 14 steps (2.1 s)**:

- no robot–robot or robot–obstacle collision,
- centroid goal progress ≥ **0.02** normalised,
- entry into the formation tube and **L = 3** consecutive steps inside it,
- no deadlock, no irreversible collapse.

Every condition is **local**. None of them requires the team to traverse anything.

## Why it is invalid

**It labels provably impossible rollouts as successes.** In the `infeasible`
scenario family — corridors **0.80–0.95 m** wide, below the **1.10 m** minimum for
a single robot *centre* to be admissible, where every policy scores **0.000
episode success** — the V1 event fired on **27.8 %** of (state, mode) pairs.

The mechanism: a team can move 0.02 normalised toward the goal and hold formation
for three consecutive steps while approaching a wall it will never pass. The
event measures short-horizon comfort, not recovery.

It also failed its own predeclared stability rule: label agreement under a single
horizon change (H = 14 → 28) was **0.749** against a required 0.80.

## What this contaminates

| File | Contamination |
|---|---|
| `recovery_signal_predictions.csv` | every `empirical_recovery_rate` and `recovered` column |
| `recovery_signal_metrics.csv` | every AUROC / AUPRC / Brier / ECE / ranking figure derived from them — including the **AUROC 0.808** reported in the Method Audit |
| `recovery_event_sensitivity.csv` | the whole V1 grid |
| `per_state_scores.csv` | `R_keep`, `R_line`, `R_split`, `best_mode`, `mode_margin`, `keep_regret`, `mode_necessity`, `qualified` |

**Consequence for earlier conclusions.** The Method Audit's headline — that the
learned score reaches AUROC 0.808 as a recovery-ranking signal — was measured
against this label. That number is **not retracted as a computation** (the
arithmetic is correct and reproducible) but it **cannot be interpreted as recovery
prediction**, because the target it predicts is not recovery. It must be
re-measured against Recovery Event V2 before any claim rests on it.

The same applies to the mode-headroom numbers in
`docs/SCENARIO_HEADROOM_REPORT.md`: `keep` being oracle-best in 82.3 % of
qualified states is a statement about the V1 label, not about task feasibility.

## Code version

Tag `scenario-headroom-v1-invalid-recovery-label`; branch `research/recovery-event-v2`
supersedes it.

## Replacement

`docs/RECOVERY_EVENT_V2_DEFINITION.md` separates three concepts the V1 event
conflated — local progress, formation recovery, and full-horizon **task**
recovery — and makes the last of these the gold standard.
