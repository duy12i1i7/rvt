# Binary Formation-Mode Pilot — Predeclared Hypothesis and Criteria

**Written and committed before any pilot training or label generation.**
Branch `research/binary-mode-pilot-v1`, from tag `recovery-event-v2-complete`.

## 1. Central hypothesis

> A graph model trained to predict candidate-conditioned **task recovery** can
> select between `keep` and `line` formation modes more effectively than
> always-keep, always-line, direct topology classification, and simple geometric
> heuristics in corridor-constrained multi-robot navigation.

## 2. Scope

**Evaluated:** (1) task-recovery prediction quality; (2) binary keep/line mode
selection; (3) closed-loop usefulness of the selected mode.

**Explicitly not evaluated, and no claim may be made about any of them:**
split mode · repeated topology switching · decentralized consensus ·
communication robustness · formal safety · formal recoverability · scalability
beyond N ∈ {4, 6}.

The switching exclusion is not stylistic: switch necessity measured **0.000 in
every family** under Recovery Event V2, so no evidence supports a switching claim.

## 3. Scenario families

| Role | Families |
|---|---|
| Primary (constrained) | `line_corridor`, `keep_line_keep` |
| Control | `keep_open`, `ambiguous` |
| OOD sanity check only | `infeasible` — false-positive probe, never in training or selection |
| **Excluded** | `split_around`, `keep_split_merge` |

Team sizes **N ∈ {4, 6}** — the range the headroom study covered. No size is added
to support a scalability claim.

## 4. Methods

**Deployable:** `always_keep` · `always_line` · `fixed_formation_expert` ·
`topology_agnostic_gnn` · `direct_keep_line_classifier` · `rvt_binary_recovery`

**Diagnostic references:** `minimum_clearance_heuristic` ·
`formation_recovery_heuristic`

**Oracle upper bounds — NOT deployable, never a competitor:**
`best_fixed_mode_per_episode_oracle` · `per_decision_rollout_oracle`

Secondary controls (optional, must not distract): Formation-aware ORCA (RVO2),
decoupled CBF-QP. **Proxy ORCA / CBF-QP / MPC are permanently excluded.**

## 5. Training and selection protocol

Three independent **model seeds** {0, 1, 2} for `topology_agnostic_gnn`,
`direct_keep_line_classifier`, `rvt_binary_recovery`, with identical optimizer-step
budget, training-data budget, validation frequency, validation episode count,
early-stopping patience, checkpoint pool size, hyperparameter budget (0 trials),
and model-selection opportunities.

Fixed across seeds: training/validation/final-test layout sets and final-test
episode seeds. Changing `model_seed` must not alter final-test episodes.

**Checkpoint selection hierarchy (predeclared, validation only):**

1. validation task-recovery **Brier score** (primary)
2. validation **candidate-ranking accuracy** (secondary)
3. validation **constrained-scenario closed-loop success** (tertiary)

Action RMSE is reported but is never a selection criterion on its own.

## 6. Loss

```
L = λ_action · L_action + λ_bce · L_task_recovery        [+ λ_rank · L_pair_rank]
```

`L_task_recovery` is BCE against the **binary Recovery Event V2 label**.
The shaped rollout utility is **not** a target — it failed its retention rule
(AUROC 0.704 vs 0.714 for minimum clearance).

**AMENDED before training (see `BINARY_MODE_LABEL_GATE_REPORT.md` §8):**
**BCE-only is the primary and sole loss for the three-seed pilot.** The pairwise
ranking term is removed from the main pilot and may be evaluated later as a
one-seed, validation-only ablation. Neither variant may be selected using
final-test results.

Rationale: the hypothesis concerns recovery-*probability* prediction and
calibration; BCE is the proper scoring rule for it, whereas a ranking term
optimises order rather than probability and would compromise the ECE measurement
in gate G1 while doubling the training runs from 9 to 18.

## 7. Primary statistical comparisons

1. `rvt_binary_recovery` vs `always_keep`
2. vs `always_line`
3. vs `direct_keep_line_classifier`
4. vs `topology_agnostic_gnn`
5. vs `minimum_clearance_heuristic`

Paired episode-level tests (matched final-test episodes): paired bootstrap CIs;
McNemar for binary outcomes; Wilcoxon signed-rank or paired permutation for
continuous. **Holm correction across the five primary comparisons.**

Across seeds: mean, SD, every individual seed, and consistency of effect direction.

**No statistical-superiority claim will be made from three seeds.** Permitted
wording: *consistent directional improvement · higher observed mean · paired
episode-level advantage · pilot evidence · no reliable difference.*

## 8. Predeclared decision gates — fixed before results

### G1 Recovery prediction
- task-recovery **AUROC ≥ 0.75**, **and**
- AUROC exceeds the minimum-clearance heuristic by **≥ 0.05**, **and**
- **ECE ≤ 0.15** with no final-test calibration fitting.

### G2 Mode selection
- higher task-recovery rate than `always_keep` on **both** constrained families;
- absolute improvement **≥ 0.05** in at least one constrained family;
- **≤ 0.03** absolute degradation vs `always_keep` on `keep_open`;
- improvement direction consistent in **≥ 2 of 3** seeds.

### G3 Mechanism
- `rvt_binary_recovery` must beat `direct_keep_line_classifier`, or show a
  meaningful calibration advantage over it. Otherwise recovery-probability
  prediction does not justify a separate contribution.

### G4 Headroom
- a visible gap must remain between deployable methods and the oracle. If the
  oracle itself has negligible advantage, the learned model is not blamed.

**These gates are pilot gates, not publication thresholds. They will not be
changed after results are observed.**

## 9. Legacy artifacts marked invalid for future scientific use

| Artifact | Status |
|---|---|
| V1 recovery labels (`results/legacy_recovery_event_v1/`) | **INVALID** — 27.8 % false positives on impassable geometry |
| Shaped-rollout-utility targets | **INVALID as a target** — AUROC 0.704 < 0.714 geometric baseline |
| Split-mode checkpoints (`rvt_swarm`, `rvt_simple_rank` with 3 modes) | **LEGACY** — split removed |
| keep/line/split selector results (`results/scenario_headroom/`, `results/method_audit/`) | **LEGACY** — 3-mode selector superseded |
| All switching-related conclusions | **INVALID** — switch necessity 0.000 under V2 |

Nothing is deleted.
