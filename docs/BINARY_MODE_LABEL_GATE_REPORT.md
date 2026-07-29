# Binary Mode Pilot — Label Quality Gate Report

Data: `results/binary_mode_pilot/{task_recovery_labels,label_statistics,label_statistics_detailed,label_joint_outcomes}.csv`
Scripts: `scripts/generate_binary_labels.py`, `scripts/analyze_binary_labels.py`
Labels: **Recovery Event V2 task recovery** (H_commit 10, T_max 120, dwell L 3, tube 1.0)

**Train and validation layouts only. Final-test layouts were not loaded. No model
was trained. The shaped rollout utility was not used.**

## 1. Scale

| | |
|---|---|
| Unique states (both modes labelled) | **759** |
| Label rows | 1 518 |
| Perturbation rollouts per state-mode | **4** |
| Total rollouts | **6 072** |
| Layout families | `line_corridor`, `keep_line_keep`, `keep_open`, `ambiguous` |
| Team sizes | 4, 6 |

## 2. Positive rates

### By split × mode

| split | mode | n | positive rate | mean empirical p |
|---|---|---|---|---|
| train | keep | 457 | 0.615 | 0.603 |
| train | line | 457 | 0.691 | 0.678 |
| val | keep | 302 | 0.623 | 0.609 |
| val | line | 302 | 0.725 | 0.710 |
| **overall** | **keep** | **759** | **0.618** | 0.606 |
| **overall** | **line** | **759** | **0.705** | 0.691 |

### By family × mode

| family | keep | line |
|---|---|---|
| `ambiguous` | 0.933 | 0.933 |
| `keep_line_keep` | **0.358** | **0.526** |
| `keep_open` | 0.993 | 0.936 |
| `line_corridor` | **0.435** | **0.586** |

### By team size × mode

| N | keep | line |
|---|---|---|
| 4 | 0.919 | 0.874 |
| 6 | **0.349** | **0.554** |

**Team size is the dominant difficulty axis.** At N = 4 almost everything succeeds;
at N = 6 keep collapses to 0.349 while line holds 0.554. The constrained families
carry the signal, exactly as designed.

### family × mode × team size × split (extract; full table in `label_statistics_detailed.csv`)

| family | mode | N | train | val |
|---|---|---|---|---|
| `line_corridor` | keep | 4 | 0.923 | 0.980 |
| `line_corridor` | keep | **6** | **0.000** | **0.000** |
| `line_corridor` | line | 4 | 0.833 | 0.860 |
| `line_corridor` | line | **6** | **0.356** | **0.383** |
| `keep_line_keep` | keep | 4 | 0.759 | 0.750 |
| `keep_line_keep` | keep | **6** | **0.000** | **0.000** |
| `keep_line_keep` | line | 4 | 0.833 | 0.778 |
| `keep_line_keep` | line | **6** | **0.200** | **0.375** |

**At N = 6 in both constrained families, `keep` never recovers — 0.000 — while
`line` recovers 20–38 % of the time.** That is the cleanest possible statement of
where keep/line headroom lives, and it is consistent across train and validation.

## 3. Joint keep/line outcomes

| scope | n | both fail | both succeed | keep only | **line only** | disagree |
|---|---|---|---|---|---|---|
| **overall** | 759 | 0.249 | 0.572 | 0.046 | **0.133** | **0.179** |
| train | 457 | 0.260 | 0.567 | 0.048 | 0.125 | 0.173 |
| val | 302 | 0.232 | 0.579 | 0.043 | 0.146 | 0.189 |
| `line_corridor` | 278 | 0.349 | 0.371 | 0.065 | **0.216** | **0.281** |
| `keep_line_keep` | 190 | 0.426 | 0.311 | 0.047 | **0.216** | **0.263** |
| `keep_open` | 141 | 0.007 | 0.936 | 0.057 | 0.000 | 0.057 |
| `ambiguous` | 150 | 0.067 | 0.933 | 0.000 | 0.000 | 0.000 |
| N = 4 | 358 | 0.028 | 0.821 | 0.098 | 0.053 | 0.151 |
| N = 6 | 401 | 0.446 | 0.349 | 0.000 | **0.204** | 0.204 |

Most decision-relevant cells:

| cell | line only | disagree |
|---|---|---|
| `line_corridor` N = 6 | **0.367** | 0.367 |
| `keep_line_keep` N = 6 | **0.270** | 0.270 |

**At N = 6, `keep_only` is exactly 0.000 in every family** — there is no state at
that team size where keeping succeeds and lining fails. Every disagreement favours
`line`.

## 4. Rollout stability

| mode | p = 0.00 | 0.25 | 0.50 | 0.75 | 1.00 | unanimous | split-decision |
|---|---|---|---|---|---|---|---|
| keep | 0.372 | 0.011 | 0.020 | 0.020 | 0.578 | **0.950** | 0.050 |
| line | 0.261 | 0.034 | 0.028 | 0.036 | 0.642 | **0.903** | 0.097 |

**95.0 % of keep and 90.3 % of line state-mode pairs are unanimous across all four
perturbed rollouts.** Exactly-ambiguous pairs (p = 0.5, where the 0.5 threshold is
a coin flip) are **2.0 %** and **2.8 %** — flagged, but small.

`line` is the noisier mode, which is mechanically sensible: single-file passage
through a gate is more sensitive to the initial perturbation than holding a
compact formation.

## 5. Split consistency

Largest train↔validation positive-rate gap: **0.066** (`keep_line_keep`, line).
**Zero flags** against the 0.20 threshold. Every family × mode pair agrees closely
across splits — notable given the layouts are *geometrically disjoint*, not merely
differently seeded.

## 6. Gates

| Gate | Requirement | Measured | Verdict |
|---|---|---|---|
| **G1** global degeneracy | 0.05 < rate < 0.95 | keep **0.618**, line **0.705** | **PASS** |
| **G2** `line_corridor` | both classes; ≥5 % disagreement; some line-only | both ✓; **0.281**; **60** line-only states | **PASS** |
| **G2** `keep_line_keep` | same | both ✓; **0.263**; **41** line-only states | **PASS** |
| **G3** control families | not rejected for keep dominance | `keep_open` keep 0.993 — expected, accepted | **PASS by rule** |
| **G4** split consistency | flag gaps > 0.20 | max gap 0.066, **0 flags** | **PASS** |
| **G5** rollout stability | report + flag near-0.5 | 90–95 % unanimous; 2.0–2.8 % at p = 0.5 | **PASS** |

**All gates pass.**

## 7. Observations that matter for the pilot, recorded now

1. **`ambiguous` produces zero disagreement (0.000).** Both modes succeed in 93.3 %
   of its states and fail together in the rest. It is a pure control: it can detect
   *harm* from mode selection but contributes nothing to the mode-selection signal.
2. **`keep_open` disagreement is 0.057, entirely `keep_only`.** Also as designed —
   choosing `line` in open field is mildly harmful, which is precisely what gate G2
   of the pilot protocol (≤ 0.03 degradation on `keep_open`) is there to police.
3. **N = 4 is nearly saturated** (both-succeed 0.821). The pilot's discriminative
   power will come almost entirely from **N = 6**. This is worth stating in advance
   so that a small overall effect is not misread — the informative subset is roughly
   the 401 N = 6 states, not all 759.
4. **No reweighting has been applied.** No class weights, no focal loss, no
   oversampling, no outcome-balanced sampling, no family weights. Family sample
   counts differ (`line_corridor` 278, `keep_open` 141) purely from layout counts
   and episode lengths.

## 8. Loss protocol amendment (predeclared, before training)

Amending `BINARY_MODE_PILOT_HYPOTHESIS.md` §6:

- **BCE-only is the primary and sole loss for the three-seed pilot**
  (`L = λ_action · L_action + λ_bce · L_task_recovery`).
- **BCE + pairwise ranking is removed from the main pilot.**
- Pairwise ranking may be evaluated later as a **one-seed, validation-only
  ablation**, after BCE has been validated.
- Neither variant may be selected using final-test results.

Rationale: the central hypothesis concerns recovery-**probability** prediction and
calibration. BCE is the proper scoring rule directly aligned with that hypothesis;
a ranking term optimises order rather than probability and would compromise the
calibration measurement (gate G1's ECE ≤ 0.15) while doubling the training runs
from 9 to 18.

This amendment is committed **before** any training begins.

---

## Recommendation

> ### **C — Labels are valid and informative. Proceed with BCE-only three-seed training.**

All five gates pass. The constrained families carry substantial, consistent
keep/line disagreement (0.281 and 0.263 overall; 0.367 and 0.270 at N = 6), the
labels are 90–95 % unanimous across perturbed rollouts, and train/validation
distributions agree to within 0.066 despite geometrically disjoint layouts.

The decisive evidence is that **at N = 6 in both constrained families, `keep`
recovers in 0.000 of states while `line` recovers in 0.200–0.383** — a genuine,
physically-grounded keep/line decision with no `keep_only` states anywhere at that
team size.

Not **A**: nothing is degenerate; global rates are 0.618 and 0.705.
Not **B**: constrained-family headroom is large, not small — 13.3 % of all states
are line-only, rising to 20.4 % at N = 6.

### One caveat carried into the pilot

The signal is concentrated at **N = 6**; N = 4 is 82 % both-succeed. Aggregate
pilot metrics will therefore dilute the effect roughly two-fold. Results must be
reported **stratified by team size**, and the N = 6 constrained-family cells are
the ones that test the hypothesis. This is stated now, before training, so it
cannot be introduced later as a post-hoc slice.

**Stopping here for approval before any training.**
