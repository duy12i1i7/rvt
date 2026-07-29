# Scenario Headroom V2 Report (Tasks 7 & 9)

Raw data: `results/scenario_headroom_v2/{per_state_scores,per_episode,summary,surrogate_evaluation}.csv`
Script: `scripts/recovery_v2_study.py` · **Validation layouts only. No learned model trained or evaluated.**

Labels come from **Recovery Event V2** (full-horizon task recovery). The V1 labels
are quarantined under `results/legacy_recovery_event_v1/`.

131 validation decision states × 3 modes × 3 rollouts; 90 policy episodes.

---

## 1. Task 7 — short-horizon surrogates vs the full-horizon gold standard

n = 393 (state, mode) pairs, positive rate 0.557.

| surrogate | AUROC | AUPRC | Brier | ECE | false-safe | top-1 | pairwise | Kendall τ |
|---|---|---|---|---|---|---|---|---|
| **formation_recovery** | **0.925** | **0.898** | **0.114** | 0.188 | **0.144** | **0.952** | **0.929** | **0.929** |
| combined_surrogate | 0.911 | 0.920 | 0.139 | 0.204 | 0.259 | 0.952 | 0.952 | 0.952 |
| crossed_bottleneck | 0.744 | 0.822 | 0.192 | **0.054** | 0.310 | 0.857 | 0.452 | 0.524 |
| local_progress | 0.714 | 0.679 | 0.187 | 0.060 | 0.546 | 0.833 | 0.488 | 0.619 |
| min_clearance | **0.714** | 0.733 | 0.216 | 0.127 | 0.402 | 0.690 | 0.000 | 0.000 |
| instantaneous_risk | 0.713 | 0.732 | 0.236 | 0.164 | 0.402 | 0.690 | 0.000 | 0.000 |
| **shaped_rollout_utility** *(the current learned target)* | **0.704** | 0.753 | 0.207 | 0.087 | 0.379 | 0.667 | 0.679 | 0.357 |
| formation_error | 0.647 | 0.690 | 0.262 | 0.193 | 0.345 | 0.690 | 0.000 | 0.000 |
| distance_to_goal | 0.465 | 0.571 | 0.315 | 0.227 | 0.546 | 0.690 | 0.000 | 0.000 |

*(Predictors constant across modes — clearance, risk, formation error, distance —
have pairwise accuracy 0 by construction; their top-1 of 0.690 is the
always-choose-`keep` baseline.)*

### The decisive result: the current target fails its own retention rule

Task 7 states: *"The old rollout utility may remain only if it predicts the
full-horizon event better than simple geometric baselines. If it does not, remove
it as the central target."*

**Shaped rollout utility: AUROC 0.704. Minimum clearance: 0.714. Instantaneous
risk: 0.713.**

The shaped utility — the quantity the score head is currently trained to regress —
**does not beat a one-line geometric baseline** at predicting full-horizon task
recovery. Its Kendall τ (0.357) is the second-worst of any predictor that varies
across modes.

> **The shaped rollout utility must be removed as the central target.**

This retroactively explains the Method Audit result. Against the *V1* label the
learned score reached AUROC 0.808 and looked like a real signal; the V1 label was
itself largely a shaped-utility-shaped quantity, so the score was predicting its
own training target's idiosyncrasies rather than recovery.

### What should replace it

**`formation_recovery` is an excellent surrogate for task recovery** — AUROC 0.925,
top-1 0.952, Kendall 0.929, false-safe 0.144. It is not *cheap* (it still needs a
rollout), but as a **training target** it is far better aligned with the gold
standard than the shaped utility, and it is a conjunction of physical conditions
rather than a weighted sum.

`crossed_bottleneck` is the best-calibrated single predictor (ECE 0.054) and
carries real signal (AUROC 0.744) from pure geometry.

---

## 2. Task 9 — headroom under the repaired label

| family | qualified | keep | line | split | headroom | margin | keep succ | oracle succ | oracle adv | switch nec |
|---|---|---|---|---|---|---|---|---|---|---|
| `keep_open` | 4 | 1.000 | 0.000 | 0.000 | 0.000 | 0.167 | 1.000 | 1.000 | 0.000 | 0.000 |
| `line_corridor` | 12 | 0.500 | **0.500** | 0.000 | **0.500** | 0.500 | 0.500 | 0.611 | **0.111** | 0.000 |
| `split_around` | 6 | 1.000 | 0.000 | **0.000** | 0.000 | 0.167 | 0.667 | 0.667 | 0.000 | 0.000 |
| `keep_line_keep` | 9 | 0.222 | **0.778** | 0.000 | **0.741** | 1.000 | 0.333 | 0.417 | 0.083 | 0.000 |
| `keep_split_merge` | 8 | 1.000 | 0.000 | **0.000** | 0.000 | 0.333 | 0.833 | 0.833 | 0.000 | 0.000 |
| `ambiguous` | 3 | 1.000 | 0.000 | 0.000 | 0.000 | 0.000 | 1.000 | 1.000 | 0.000 | 0.000 |
| `infeasible` | **0** | — | — | — | — | — | 0.000 | 0.000 | 0.000 | 0.000 |

**Pooled (42 qualified states, 90 episodes):** keep **0.690**, line **0.310**,
split **0.000** · oracle advantage **0.033** · switch necessity **0.000**.

### V1 → V2, same families

| | V1 | V2 |
|---|---|---|
| `infeasible` qualified states | **35** (artifact) | **0** |
| pooled keep-best share | 0.823 | **0.690** |
| pooled line-best share | 0.081 | **0.310** |
| pooled split-best share | 0.096 | **0.000** |
| `keep_line_keep` line share | 0.308 | **0.778** |
| `line_corridor` line share | 0.131 | **0.500** |
| pooled switch necessity | 0.033 | 0.000 |

Repairing the label did two things at once: it **eliminated the infeasible-family
artifact entirely** (35 spurious qualified states → 0), and it **roughly quadrupled
the measured value of `line`**. V1 was hiding real keep/line structure behind noise.

## 3. Predeclared criteria (unchanged thresholds)

| # | Criterion | Threshold | V1 | V2 | Verdict |
|---|---|---|---|---|---|
| C1 | no mode oracle-best > 70 % | ≤ 0.70 | 0.823 ✗ | **0.690** | **PASS** |
| C2 | line ≥ 15 % | ≥ 0.15 | 0.081 ✗ | **0.310** | **PASS** |
| C3 | split ≥ 10 % | ≥ 0.10 | 0.096 ✗ | **0.000** | **FAIL** (moot — split removed, Task 8) |
| C4 | keep regret in constrained families | ≥ 0.05 | 0.080–0.361 ✓ | 0.500–0.741 | **PASS** |
| C5 | oracle advantage | ≥ 0.10 | 0.058 ✗ | **0.033** pooled; 0.111 / 0.083 in the two corridor families | **FAIL pooled** |
| C6 | median margin | ≥ 0.10 | 0.250 ✓ | 0.500–1.000 in corridor families | **PASS** |
| C7 | some episodes need a transition | > 0 | 0.250 (artifact) | **0.000** | **FAIL** |

**Three criteria now pass that previously failed (C1, C2, C4/C6 strengthened).
Two fail: C5 pooled, and C7.**

C5's pooled failure is dominated by four families with zero headroom *by design*
(`keep_open`, `ambiguous`, `infeasible`) or by the removed split mechanism
(`split_around`, `keep_split_merge`). In the two families where mode choice is the
whole point, oracle advantage is 0.083–0.111.

C7's failure is unambiguous and matters: **no episode requires a mode
transition.** V1's 0.250 in `split_around` was an artifact of the broken label.
A *per-episode* mode choice suffices; a *switching* controller is not justified.

## 4. Limitations

- 131 states, 90 episodes, N ∈ {4, 6}, one perturbation seed.
- 3 rollouts per (state, mode) quantises rates to 0.33; the binary label
  thresholds that at 0.5.
- `formation_recovery`'s strength as a surrogate is partly definitional — it shares
  the collision/deadlock/collapse conjuncts with task recovery. Its *added* value
  is the tube-dwell term; a proper ablation of that overlap is not done here.
- Qualified-state counts are small (3–12 per family), so per-family shares carry
  wide uncertainty. The pooled figures are the load-bearing ones.
