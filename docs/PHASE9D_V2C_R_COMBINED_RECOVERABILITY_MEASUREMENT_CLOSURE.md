# Phase 9D-V2C-R — Combined Recoverability V2 Measurement Closure

**Verdict A — the missing measurements expose a frozen gate failure.
Recommendation: `DO_NOT_TRAIN`.**

The target came back, every outstanding measurement was completed, and eight of
the nine frozen Recoverability label-audit gates resolved in the dataset's
favour. **Frozen gate 7 does not hold.** TRAIN F9/LINE shows stochastic label
instability of **59/530 = 0.11132075** against a permitted maximum of **0.10**.

This was the one gate that had never been evaluated for V2 in any phase. It has
now been measured by full census, and it fails.

Nothing else changed: the sealed data are byte-perfect, the arithmetic
reconciles exactly, the validation adequacy gate passes for all ten primary
families, and the F3/F4/F6 scenario resolution is independently confirmed rather
than disturbed.

---

## 1. Target and handoff

| item | value |
|---|---|
| HEAD | `e7c3e33aa43ac46b075ddd448b3629eb8e3b3b0b` ✓ clean |
| branch | `research/rvt-phase9d-v2c-r-measurement-closure-v1` |
| target | `100.71.102.9` — **reachable** |
| image | `sha256:2949628f6eb57abafe680687b677958c7cc52bffab84545514a48d84a936c684`, not rebuilt |
| official mounts | **read-only** (`:ro`) for both TRAIN and VALIDATION |

**Resume scripts inspected before execution**, as required. Each has exactly two
write operations — one `mkdir` and one `write_text` — both targeting a separate
output mount. TRAIN and VALIDATION are bind-mounted read-only, so a write is
impossible at the container boundary as well as absent from the code.

## 2. Sealed data — byte-verified

| | TRAIN | VALIDATION |
|---|---|---|
| shards verified | **44 / 44** | **12 / 12** |
| byte mismatches | **0** | **0** |
| rows counted / declared | 90,294 / 90,294 | 23,220 / 23,220 |
| bytes counted / declared | 1,674,191,736 ✓ | 445,716,747 ✓ |
| composite seal | `a966f318…` ✓ | `667b1175…` ✓ |
| all six roots | match | match |
| duplicate row ids | 0 | 0 |
| row validation failures | 0 | 0 |

`SEALED_DATASET_INTEGRITY_FAILURE`: **no**.

**Row root algorithm (R15)** read from the contract before use:
`sha256_document(sorted(scientific_row_id))`, recomputed by streaming every
sealed shard. Shard-hash aggregation was **not** substituted. TRAIN recomputes to
`c91414f5…` and VALIDATION to `28d52af9…`, both matching.

## 3. Gate 7 — stochastic label instability — **FAIL**

### Exact frozen definition, recovered before computing anything

| field | value |
|---|---|
| statement | "stochastic label instability is at most 0.10 per family/candidate" |
| authority | `docs/RVT_RECOVERABILITY_LABEL_AUDIT_GATES.md` (hash matches the H1 requirement map) |
| implementation | `scripts/audit_phase9d_r_dataset_readonly.py` |
| unstable aggregate | replica labels not all equal — `len(set(replica_labels)) > 1` |
| denominator | aggregates with more than one replica (`stochastic_aggregate_totals`) |
| unit | (family, candidate) |
| statistic | **maximum** rate over (family, candidate) |
| threshold | **≤ 0.10** |
| escape clause | **none** (gate 3 has one; gate 7 does not) |
| pre-data status | frozen before any V2 row existed |

### Full census — every F8/F9 aggregate in both splits, no sampling

| split | family | candidate | stochastic aggregates | replicas | unstable | rate | |
|---|---|---|---:|---:|---:|---:|:--:|
| train | F8 | COMPACT | 567 | 1,701 | 41 | 0.07231041 | pass |
| train | F8 | LINE | 567 | 1,701 | 35 | 0.06172840 | pass |
| train | F9 | COMPACT | 530 | 1,590 | 0 | 0.00000000 | pass |
| **train** | **F9** | **LINE** | **530** | **1,590** | **59** | **0.11132075** | **FAIL** |
| validation | F8 | COMPACT | 147 | 441 | 8 | 0.05442177 | pass |
| validation | F8 | LINE | 147 | 441 | 3 | 0.02040816 | pass |
| validation | F9 | COMPACT | 138 | 414 | 0 | 0.00000000 | pass |
| validation | F9 | LINE | 138 | 414 | 8 | 0.05797101 | pass |

**Maximum = 0.11132075 > 0.10 → gate 7 FAILS.** Seven of eight cells are inside
the threshold; one is not. At 530 aggregates the threshold permits 53 unstable;
59 were observed — **six over**.

### Why I trust the measurement

- **Full census**, not a sample: 2,194 TRAIN + 570 VALIDATION candidate
  aggregates — every one that carries more than one replica.
- **The replay is faithful.** All 2,194 TRAIN and 570 VALIDATION replayed
  aggregates reproduce the sealed ledger's label *and* disposition exactly: **0
  mismatches, 0 events absent**. The instability is a property of the sealed
  dataset, not an artefact of replaying it.
- **Cross-checked**: the denominator 530 equals TRAIN F9's selected event count
  from the independent Stage-A/ledger accounting, and replicas = 3 × aggregates.

### Where it sits (observation, not justification)

TRAIN F9/COMPACT has a positive rate of 0.1038 and **zero** replica
disagreement; TRAIN F9/LINE has a positive rate of 0.4792 and 0.1113
disagreement. F9 is `DYNAMIC_LOCAL_OBSTACLE`, whose moving obstacle is the
intended stochastic element, and all-success aggregation is most sensitive to
replica variation where a candidate's outcome sits near an even split.

That explains *where* the failure is. It is not a reason to discount it, and I
have not treated it as one.

### What I did not do

No threshold tuning. No reinterpretation of "instability". No exclusion of F9 or
of the LINE candidate. No regeneration or resampling. The gate document is
explicit: *"A failed gate blocks training; it does not authorize geometry, target
or threshold tuning against model results."*

## 4. Replica arithmetic (R3) — exact

| split | 1-replica aggregates | 3-replica aggregates | computed | declared | |
|---|---:|---:|---:|---:|:--:|
| TRAIN | 7,870 × 1 | 2,194 × 3 = 6,582 | **14,452** | 14,452 | ✓ |
| VALIDATION | 2,000 × 1 | 570 × 3 = 1,710 | **3,710** | 3,710 | ✓ |
| combined | | | **18,162** | 18,162 | ✓ |

No approximation.

## 5. Gate 8 — distribution shift — **PASS**

Both frozen components, recomputed from the sealed data rather than accepted
from the prior descriptive report.

**Rate component.** Statistic: max over {COMPACT, LINE} of
|train rate − validation rate|.

| candidate | TRAIN | VALIDATION | difference |
|---|---:|---:|---:|
| COMPACT | 0.351351351351 | 0.383657587549 | 0.032306236197 |
| LINE | 0.278219395866 | 0.316731517510 | **0.038512121643** |

Gate statistic **0.038512121643** ≤ 0.15 → **PASS**. The prior report's 0.032 and
0.039 were the two per-candidate differences; the frozen statistic is their
maximum.

**Divergence component.** Exact convention recovered from
`scripts/build_phase9d_r_recoverability_audit.py::_js_divergence`:

- category order frozen as `(BOTH_SUCCESS, COMPACT_ONLY_SUCCESS, LINE_ONLY_SUCCESS, BOTH_FAIL)`
- each distribution normalised by its own event total
- **logarithm base 2**
- **no smoothing** — terms with `p_i == 0` are skipped
- `JS = 0.5·KL(p‖m) + 0.5·KL(q‖m)`, `m = (p+q)/2`
- no library default used

p (TRAIN) = [0.13175676, 0.21959459, 0.14646264, 0.50218601]
q (VALIDATION) = [0.13073930, 0.25291829, 0.18599222, 0.43035019]

**JS divergence base 2 = 0.004546838319** ≤ 0.15 → **PASS**, a 33× margin.

**Gate 8 result: PASS.**

## 6. Per-family shift (R6) — remains descriptive

No predeclared per-family label-rate gate exists in
`RVT_RECOVERABILITY_LABEL_AUDIT_GATES.md` or the H1 requirement map. The
descriptive F10/LINE ≈ 0.2018 and F2/COMPACT ≈ 0.1811 were **not** converted into
a gate.

## 7. Joint Recoverability outcomes (R7/R8) — exact, not estimated

Measured from paired candidate labels on the same sealed event. These are
**observed Recoverability decision-event categories**, not scenario-manifest
headroom categories.

| category | TRAIN | VALIDATION | combined |
|---|---:|---:|---:|
| `RECOVERABILITY_EVENT_BOTH_SUCCESS` | 663 | 168 | 831 |
| `RECOVERABILITY_EVENT_COMPACT_ONLY_SUCCESS` | 1,105 | **325** | 1,430 |
| `RECOVERABILITY_EVENT_LINE_ONLY_SUCCESS` | 737 | **239** | 976 |
| `RECOVERABILITY_EVENT_BOTH_FAIL` | 2,527 | 553 | 3,080 |
| **events** | **5,032** | **1,285** | **6,317** |

The prior phase's marginal-based lower bounds (COMPACT_ONLY ≥ 216, LINE_ONLY ≥
130) **held** against the measured 325 and 239.

**Gate 2 (R9) now measured, not bounded**: TRAIN 1,105 / 737 against a minimum of
50; VALIDATION 325 / 239 against a minimum of 20. **PASS.**

## 8. Target V4 predicate decomposition (R10) and control (R14)

Repository-authoritative predicate names from
`CandidateReplicaResult.failed_predicates`. Read-only replay, 0 rows written,
determinism perfect.

**VALIDATION F3/F4/F6 — both candidates:**

| cell | events | positives | `downstream_goal_complete` failures | safety-infeasible |
|---|---:|---:|---|---|
| F3/COMPACT | 13 | 0 | 13/13 | 13/13 |
| F3/LINE | 13 | 0 | 13/13 | 13/13 |
| F4/COMPACT | 10 | 0 | 10/10 | 10/10 |
| F4/LINE | 10 | 0 | 10/10 | 10/10 |
| F6/COMPACT | 17 | 0 | 17/17 | 17/17 |
| F6/LINE | 17 | 0 | 17/17 | 17/17 |

Terminations are `COLLISION` throughout (F6/LINE adds 3 `HORIZON_COMPLETE`).
**The TRAIN mechanism reproduces exactly on disjoint layouts.** No relabelling.

**F1 positive control, VALIDATION**: COMPACT **16/18 positive**, LINE **7/18
positive**, through the identical frozen code path. The label path is not
degenerate. No tuning.

## 9. F10/COMPACT (R11)

| | TRAIN | VALIDATION |
|---|---|---|
| COMPACT positive / negative | **0** / 439 | **0** / 113 |
| LINE positive / negative | 94 / 345 | 47 / 66 |
| joint `COMPACT_ONLY_SUCCESS` | 0 | 0 |
| joint `LINE_ONLY_SUCCESS` | 94 | 47 |

**Mechanism**: F10/COMPACT reaches `GOAL_COMPLETE` in a minority of replayed
replicas (3/15 TRAIN, 4/14 VALIDATION) yet is still a valid task negative,
because the Target V4 conjunction additionally requires
`target_metric_v3_dwell_complete` and `safety_projection_resolved`, which fail;
safety infeasibility at the decision state is 100 %.

**Violates no existing frozen gate.** All nine were checked. No
positive-per-family requirement was invented. This matches the measured
pre-data headroom, which records F10 as BOTH_FAIL 12 + LINE_ONLY_SUCCESS 3 — no
COMPACT_ONLY or BOTH_SUCCESS cell.

## 10. Feature schema (R12/R16)

Tensors read at `graph_payload['tensors']` — the earlier wrong-key bug was **not**
repeated.

| | TRAIN | VALIDATION | combined |
|---|---|---|---|
| rows | 90,294 | 23,220 | **113,514** ✓ |
| node feature dim | 35 (all) | **35 (all)** | uniform |
| edge feature dim | 19 (74,320) | **19 (19,274)** | uniform |
| zero-edge rows | 15,974 | 3,946 | contract-valid |
| zero-node rows | 0 | 0 | 0 |
| non-finite values | 0 | **0** | **0** |
| mask length violations | 0 | **0** | **0** |
| mask occupancy (node/edge) | 1.0 / 1.0 | 1.0 / 1.0 | — |
| feature schema hashes | 1 | 1 | **same hash both splits** |
| COMPACT / LINE rows | 45,147 / 45,147 | 11,610 / 11,610 | balanced |
| candidate groups with wrong row count | 0 | 0 | 0 |
| row identity failures | 0 | 0 | 0 |

Single feature schema hash `1ea52c6a…` across both splits.

## 11. Graph and structural distributions (R13/R17) — descriptive

| | TRAIN | VALIDATION |
|---|---:|---:|
| mean node count | 13.7145 | 14.2600 |
| mean edge count | 25.4290 | 26.5201 |
| mean degree | 2.9594 | 2.9873 |
| eligible states / episode | 8.4133 | 9.0467 |
| selected events / episode | 4.1933 | 4.2833 |
| terminal `COLLISION` / `GOAL_COMPLETE` | 710 / 458 | 160 / 133 |

Design is uniform by construction in both splits (family, N, source policy).
**No structural incompatibility found.** No new statistical gate created.

**Split hygiene, measured on all eight identity axes — overlap 0 on every one**,
including scientific row ids (90,294 vs 23,220), event ids, source-state
fingerprints, acquisition hashes, seed streams, layout ids and layout hashes.
That closes gate 9 at row level.

## 12. Complete frozen gate table (R19)

| gate | definition | threshold | TRAIN | VALIDATION | combined | result |
|---|---|---|---|---|---|:--:|
| 1 | each candidate has both classes | ≥1 each | C 1768/3264, L 1400/3632 | C 493/792, L 407/878 | C 2261/4056, L 1807/4510 | **PASS** |
| 2 | decisive-category minimums | train ≥50, val ≥20 | 1105 / 737 | 325 / 239 | 1430 / 976 | **PASS** |
| 3 | candidate positive rate in [0.10, 0.90] | [0.10, 0.90] | 0.3514 / 0.2782 | 0.3837 / 0.3167 | 0.3579 / 0.2861 | **PASS** |
| 4 | ≥30 validation events per primary family | ≥30 | n/a | min F4 = 77 | n/a | **PASS** |
| 5 | zero N=24 rows | 0 | 0 | 0 | 0 | **PASS** |
| 6 | invalid rollout rate | <0.02 / <0.05 | 0.0 | 0.0 | 0.0 | **PASS** |
| **7** | **stochastic label instability** | **≤0.10** | **F9/LINE 0.11132075** | max 0.05797 | max **0.11132075** | **FAIL** |
| 8 | rate difference and JS divergence | ≤0.15 / ≤0.15 | — | — | 0.038512 / 0.004547 | **PASS** |
| 9 | event split and geometry leakage | 0 | — | — | 0 on all 8 axes | **PASS** |

**Gates measured: 9/9. Not evaluated: none. Passing: 1–6, 8, 9. Failing: 7.**

## 13. Scenario semantics (R18) — preserved, and independently reinforced

Not reopened. **`H2_EPISODE_HEADROOM != H1_MID_TRAJECTORY_RECOVERABILITY_LABEL`**
stands, and F3/F4/F6 remain
**`LEGITIMATE_STRUCTURAL_ONE_CLASS_REGION_COMPATIBLE_WITH_H1`**.

The new measurements *confirm* rather than disturb this:

- VALIDATION F3/F4/F6 fail `downstream_goal_complete` in 100 % of replayed
  replicas on both topologies, with 100 % safety infeasibility — the TRAIN
  mechanism, on disjoint layouts.
- The VALIDATION F1 positive control produces positives through the same path.
- The **15 cells where both candidates are zero-positive are identical
  cell-for-cell** in TRAIN and VALIDATION: F3/N5–N16, F4/N5–N12, F6/N5–N16, and
  **F10/N16**.

**The gate 7 failure is unrelated to this question.** Gate 7 constrains
replica-to-replica agreement within a candidate aggregate and can only be
evaluated on F8 and F9 — the two families that run three replicas. F3, F4 and F6
run a single replica and are not measurable by it. The failing cell is F9/LINE, a
family with a healthy positive rate.

## 14. Training pipeline (R20) and no-mutation (R22/R23)

`TRAINING_PIPELINE_NOT_V2_READY` — **confirmed only**, not implemented. Training
operations 0, probe models 0, HP trials 0. Moot for now: a failed frozen gate
blocks training regardless of loader readiness.

| | before | after |
|---|---:|---:|
| TRAIN files / shards | 61 / 44 | 61 / 44 |
| VALIDATION files / shards | 23 / 12 | 23 / 12 |
| TRAIN seal | `a966f318…` | unchanged |
| VALIDATION seal | `667b1175…` | unchanged |

Study-A N24 **0** · Study-B **0** · final test **0** · training **0** · HP **0** ·
Residual **0** · new official rows **0** · V1 mutations **0**.

---

## Final dataset classification

**`RECOVERABILITY_V2_DATASET_ADEQUATE_WITH_DECLARED_STRUCTURAL_REGIONS`**

This describes the dataset's scientific *structure*: seals, accounting, split
hygiene, schema, adequacy gate and the declared structural one-class regions are
all sound. **It is not a training authorization.**

## Verdict

**A — the missing measurements expose a frozen gate failure.**

Completing the measurement gap resolved eight of nine frozen gates in the
dataset's favour, but frozen label-audit gate 7 fails in TRAIN F9/LINE at
59/530 = 0.11132075 against a permitted 0.10. The measurement is a full census,
the replay reproduced every sealed label and disposition exactly, and gate 7
carries no scientific-scope escape clause.

Not C: C requires that *all* frozen gates are measured **and pass**.

Not E: nothing remains unmeasured — the outstanding list is empty.

Not D: no data-integrity defect exists; the sealed data are byte-perfect.

Not B: this is not a judgement call about sound science — a predeclared gate is
breached, and the gate document says a failed gate blocks training.

**Recommendation: `DO_NOT_TRAIN`.**

### What this does and does not mean

It does **not** invalidate the sealed datasets, the combined arithmetic, the
validation adequacy gate, or the resolved F3/F4/F6 semantics.

It **does** mean a predeclared data-quality gate that had never been evaluated
for V2 is now evaluated and does not hold, so training is blocked until the owner
decides how to proceed under the frozen rules.

Explicitly **not** exercised here, and not to be inferred from this result:
tuning the 0.10 threshold, reinterpreting the instability definition, excluding
F9 or the LINE candidate, regenerating or resampling F9, or treating the
VALIDATION F9/LINE pass at 0.058 as sufficient. Any amendment to a frozen gate
requires owner scientific authority and must not be decided from the result that
the gate caught.

No training, no HP search, no Residual, no N24, no Study-B, no final test.
