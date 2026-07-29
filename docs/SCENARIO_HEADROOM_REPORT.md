# Scenario Headroom Report (Tasks 5 & 6)

Raw data: `results/scenario_headroom/{per_state_scores,per_episode,summary}.csv`
Script: `scripts/qualify_scenarios.py` · **No learned model was used.**
Criteria fixed in advance: [`MODE_HEADROOM_DEFINITION.md`](MODE_HEADROOM_DEFINITION.md)

**Validation layouts only** (15 layouts × 7 families, N ∈ {4, 6}). 619 decision
states, 334 qualified; 120 episodes per policy. Final-test layouts were never
loaded.

---

## 1. Results by family

`qual` = qualified states · `keep/line/split` = share of qualified states where
that mode is oracle-best · `headrm` = selector headroom · `margin` = median mode
margin · `necess` = mode necessity · `keepS`/`oracS` = episode success for
always-keep and the rollout oracle · `swNec` = switch necessity.

| family | qual | keep | line | split | headrm | margin | necess | keepS | oracS | oracAdv | swNec |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `keep_open` | 41 | 0.902 | 0.000 | 0.098 | 0.098 | 0.000 | 0.098 | 1.000 | 1.000 | 0.000 | 0.000 |
| `line_corridor` | 61 | 0.770 | **0.131** | 0.098 | 0.221 | 1.000 | 0.230 | 0.458 | 0.583 | **0.125** | 0.000 |
| `split_around` | 45 | 0.867 | 0.044 | 0.089 | 0.128 | 0.250 | 0.133 | 0.750 | 0.938 | **0.188** | **0.250** |
| `keep_line_keep` | 52 | **0.615** | **0.308** | 0.077 | **0.361** | 0.750 | 0.365 | 0.312 | 0.375 | 0.062 | 0.000 |
| `keep_split_merge` | 56 | 0.911 | 0.018 | 0.071 | 0.080 | 0.000 | 0.089 | 0.875 | 0.875 | 0.000 | 0.000 |
| `ambiguous` | 44 | 0.909 | 0.000 | 0.091 | 0.091 | 0.000 | 0.091 | 1.000 | 1.000 | 0.000 | 0.000 |
| `infeasible` | 35 | 0.829 | 0.000 | 0.171 | 0.150 | 1.000 | 0.171 | 0.000 | 0.000 | 0.000 | 0.000 |

**Pooled:** 334/619 states qualified (0.540) · best-mode = keep 0.823, line 0.081,
split 0.096 · selector headroom 0.167 · median margin 0.250 · mode necessity 0.174
· oracle advantage **0.058** · switch necessity 0.033 · mean oracle switches 1.63.

## 2. Qualification criteria — pooled verdict

| # | Criterion | Threshold | Measured | Verdict |
|---|---|---|---|---|
| C1 | no mode oracle-best in > 70 % of qualified states | ≤ 0.70 | keep **0.823** | **FAIL** |
| C2 | ≥ 15 % of qualified states prefer `line` | ≥ 0.15 | **0.081** | **FAIL** |
| C3 | ≥ 10 % prefer `split` | ≥ 0.10 | **0.096** | **FAIL** (marginal) |
| C4 | always-keep has measurable regret in constrained families | ≥ 0.05 | 0.080–0.361 | **PASS** |
| C5 | oracle beats always-keep | ≥ 0.10 | pooled **0.058** | **FAIL** (passes in 2 families) |
| C6 | margins not all near zero | ≥ 0.10 | 0.250 | **PASS** |
| C7 | some episodes require a transition | > 0 | 0.250 in `split_around` | **PASS** |

**Four of seven fail. The benchmark does not qualify as designed.**

Thresholds are not being revised. C1–C3 and C5 fail, and that is the result.

## 3. A benchmark defect the `infeasible` family exposed

`infeasible` gates are **0.80–0.95 m wide**, below the 1.10 m minimum for a single
robot centre to pass. Episode success is **0.000 for every policy**, confirming the
geometry. Yet the family reports **35 qualified states**, a median mode margin of
**1.000**, and split preferred in 17.1 % of them.

The recovery-event sensitivity study confirms the cause directly:

```
S5  infeasible-family positive rate (<= 0.05):  0.278   FAIL
```

**27.8 % of (state, mode) pairs in a physically impassable corridor are labelled
"recovered".** The horizon-14 event asks only whether the team moves 0.02
normalised progress and holds formation for 3 consecutive steps — which it can do
while approaching a wall it will never pass. The event is **local**, and it does
not reflect episode-level feasibility.

This invalidates the `infeasible` family's numbers *and* casts doubt on the
constrained families, where the same locality inflates apparent recovery near
obstacles the team has not yet reached.

## 4. Recovery-event stability (Task 7)

| grid point | positive rate | stability vs default | non-uniform states |
|---|---|---|---|
| **H=14, tube 1.00, L=3, prog 0.02 (default)** | **0.535** | — | 0.546 |
| H=7 | 0.344 | 0.790 | 0.567 |
| H=28 | 0.620 | **0.749** | 0.555 |
| tube 0.75 | 0.420 | 0.885 | 0.718 |
| tube 1.50 | 0.706 | 0.829 | 0.417 |
| L=1 | 0.623 | 0.912 | 0.454 |
| L=5 | 0.458 | 0.923 | 0.669 |
| prog 0.01 | 0.562 | 0.972 | 0.546 |
| prog 0.05 | 0.475 | 0.941 | 0.583 |

| Rule | Threshold | Measured | Verdict |
|---|---|---|---|
| S1 not too easy | ≤ 0.85 | 0.535 | PASS |
| S2 not too rare | ≥ 0.15 | 0.535 | PASS |
| S3 label stability | ≥ 0.80 | worst **0.749** (H=28) | **FAIL** |
| S4 discriminative | ≥ 0.20 | 0.546 | PASS |
| S5 infeasible sanity | ≤ 0.05 | **0.278** | **FAIL** |

**The recovery event fails two of its own predeclared criteria.** Horizon is the
sensitive axis: moving H from 14 to 28 flips 25 % of labels. Tube tolerance and
dwell are comparatively stable (0.83–0.92); progress is very stable (0.94–0.97).

## 5. Scenario classification (Task 6)

| Family | Class | Reason |
|---|---|---|
| `keep_open` | **B — valid but low-headroom** | Works exactly as designed: keep dominates (0.902), oracle advantage 0.000, both at ceiling success 1.000. A correct null, useless for studying selection |
| `line_corridor` | **A — valid and informative** | Oracle advantage 0.125, headroom 0.221, margin 1.000, and the highest `line` share outside the transition family. The clearest single-mode signal |
| `split_around` | **A — valid and informative** | Largest oracle advantage (0.188) and the **only** family with non-zero switch necessity (0.250). But `split` is oracle-best in only 8.9 % of states — the advantage comes from *switching*, not from split *per se* |
| `keep_line_keep` | **A — valid and informative** | Best mode diversity by far (keep 0.615 / line 0.308), highest headroom (0.361) and necessity (0.365) — the only family passing C1 |
| `keep_split_merge` | **F — redundant / D — no headroom** | Intended split-favourable, but keep dominates 0.911, headroom 0.080, oracle advantage **0.000**, margin 0.000. Keep simply drives through. The blocker geometry does not force a split |
| `ambiguous` | **B — valid but low-headroom**, working as intended | Margin 0.000, oracle advantage 0.000, ceiling success. Confirms ties are detected; contributes nothing to selection |
| `infeasible` | **E — dominated by simulator artifact** | Episode success 0.000 everywhere (geometry correct), but 27.8 % of rollouts labelled recovered. Its state-level numbers must be **discarded**, not interpreted |

### Rejections and revisions required

- **`keep_split_merge` is rejected** for the pilot: it does not create the split
  headroom it was designed for. Either the blocker must be widened so `keep`
  genuinely cannot pass, or the family is dropped.
- **`infeasible` state-level labels are rejected** until the recovery event is
  made non-local. Its *episode-level* result (0.000 success for all policies) is
  valid and worth keeping as a sanity check.
- **`ambiguous` and `keep_open` are retained as controls only**, never as evidence
  about selection.

**No scenario was selected for making any method look good** — no method was run.

## 6. The geometric tightness that was flagged in advance

`SCENARIO_FAMILY_SPECIFICATION.md` §C warned that the `split` template's lane
offset (0.65 m) clears the central obstacle by only 0.10 m beyond `d_ro`. The
result is consistent with that warning: `split` is oracle-best in only 8.9 % of
`split_around` states despite being the only geometrically admissible mode by
hypothesis. **The measurement contradicts the hypothesis**, and per the
specification the measurement wins.

The most likely reading is that the fixed 1.30 m lane gap is too narrow to make
splitting genuinely advantageous, so `keep` squeezes past the obstacle instead.
Testing that would require changing the split template — a method change, out of
scope here, and one that must not be made by tuning against a target result.

## 7. Summary

The benchmark **as designed does not qualify**. Mode selection headroom exists but
is small and concentrated: only `keep_line_keep`, `line_corridor` and
`split_around` carry usable signal, `keep` remains oracle-best in 82.3 % of
qualified states, and the pooled oracle advantage is 0.058 against a 0.10
threshold. Separately, the recovery event is too local to be trusted near
infeasible geometry.
