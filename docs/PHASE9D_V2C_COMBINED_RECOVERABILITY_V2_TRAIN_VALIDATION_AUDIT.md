# Phase 9D-V2C — Combined Official Recoverability V2 TRAIN + VALIDATION Scientific Adequacy Audit

**Verdict E — audit incomplete.** Every scientific question this phase poses is
answered from committed authority, and the F3/F4/F6 scenario tension that TRAIN
and VALIDATION both carried forward is **resolved**. But the production target
holding the sealed row payloads and stage ledgers went unreachable partway
through and stayed down for the entire measurement window, so several required
recomputations *from the actual data* — and frozen label-audit **gate 7** in
particular — could not be performed. Verdict C asserts adequacy "under all
frozen criteria"; that is not yet established, so I am not claiming it.

**Everything outstanding is measurement, not analysis.** The scripts are
written and staged; they need one reachable host.

---

## 1. Handoff and scope

| item | value |
|---|---|
| HEAD | `ae45f954750657e594a04341a98f7f267028b8b3` ✓ |
| tree | clean ✓ |
| TRAIN closure commit | `904d96d84a9ad04fee02bdafb8c0d0023369ec03` ✓ present |
| TRAIN audit commit | `606f443a315830b0258ed42b24d894e84b98cc6c` ✓ present |
| branch created | `research/rvt-phase9d-v2c-combined-recoverability-audit-v1` |
| commits after VALIDATION closure | **0** |

No data generated, no model trained, no HP search, no Residual, no N24, no
Study-B, no final test.

## 2. Dataset identity

| item | value |
|---|---|
| TRAIN composite seal | `a966f318832fb60bd99acdfdff72f0c7011d730f3e0fb51494ce318210f39bba` |
| VALIDATION composite seal | `667b117555a65ad9da7f8e6e7f71b2cfb6843cc66d8e8c35eb68650b7818ca69` |
| **combined development root** | **`0a76ee0ea37b6f7c1c3c15966ae6d7b685c0bb8bcbbcd8717bb0922905b4b731`** |
| Source-Acquisition Protocol V2 | `19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d` |
| Target V4 | `54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee` |
| Row Binding V2 (full) | `98f18a94c6a69d27a4cbf38169ca15e998ce4b4adfbba9a48cb1b3233391adf8` |
| qualified image | `sha256:2949628f6eb57abafe680687b677958c7cc52bffab84545514a48d84a936c684` |
| image source commit | `f0a923f57fd8bea6b8249fad9652fcd37c674740` |

**Both composite seals were recomputed independently** from the declared roots
plus the frozen contracts, image digest, profile and exclusion-union hash, and
both reproduce exactly. All three scientific contract hashes are byte-identical
across the two splits. The combined root **references** the two seals and
rewrites neither dataset.

All eight authority documents named by the H1 requirement map hash-match their
recorded values — no authority has drifted.

### Not verified in this phase

Shard-byte verification of the 56 shards and recomputation of the two row
dataset roots from row bytes. Those were performed on target during Phase
9G-V2A-V (TRAIN 44/44 byte-identical before *and* after the VALIDATION run;
VALIDATION's 23,220 rows re-validated in-image at generation) and are committed,
but this phase did not repeat them.

## 3. Accounting — all seven declared identities verify

Recomputed by summing the **per-cell** family × N tables in the two sealed
closure artifacts, independently of the reported totals.

| quantity | TRAIN | VALIDATION | combined | declared | |
|---|---:|---:|---:|---:|:--:|
| source episodes | 1,200 | 300 | **1,500** | 1,500 | ✓ |
| eligible realized states | 10,096 | 2,714 | 12,810 | — | |
| selected source events | 5,032 | 1,285 | **6,317** | 6,317 | ✓ |
| candidate aggregates | 10,064 | 2,570 | **12,634** | 12,634 | ✓ |
| candidate replica executions | 14,452 | 3,710 | **18,162** | 18,162 | ✓ |
| positive aggregates | 3,168 | 900 | **4,068** | 4,068 | ✓ |
| valid-negative aggregates | 6,896 | 1,670 | **8,566** | 8,566 | ✓ |
| actual `GENERATION_INVALID` | 0 | 0 | **0** | — | |
| retained pair events | 5,032 | 1,285 | 6,317 | — | |
| robot-local rows | 90,294 | 23,220 | **113,514** | 113,514 | ✓ |

Aggregates = 2 × events in both splits and combined. Positive + valid-negative +
invalid = aggregates in both splits and combined.

## 4. Effective scientific sample size (C4)

**The 113,514 robot-local rows are not 113,514 independent observations.**
`phase9d_recoverability_statistical_unit_v1.json` freezes
`robot_local_rows_statistically_independent = false` and
`raw_row_mean_permitted = false`, with clustering keys
`(split, layout_sha256, source_episode_id, decision_event_id)`.

| level | TRAIN | VALIDATION | combined |
|---|---:|---:|---:|
| source episode | 1,200 | 300 | 1,500 |
| eligible realized source state | 10,096 | 2,714 | 12,810 |
| **selected source decision event** | **5,032** | **1,285** | **6,317** |
| retained candidate-pair event | 5,032 | 1,285 | 6,317 |
| candidate aggregate | 10,064 | 2,570 | 12,634 |
| candidate replica execution | 14,452 | 3,710 | 18,162 |
| robot-local scientific row | 90,294 | 23,220 | 113,514 |

The primary clustered unit is the **decision event**. Rows inflate the apparent
sample by **17.97×**.

## 5. Split hygiene (C3)

| axis | TRAIN | VALIDATION | overlap |
|---|---:|---:|---:|
| `layout_id` | 20 | 10 | **0** |
| `layout_sha256` | 20 | 10 | **0** |
| source-episode identity | 1,200 | 300 | **0** |
| exclusion-union identities | — | 380 | **0** |
| duplicate source identity | — | — | **0** |

Verified from the frozen manifests and the committed pre-launch audit. Random
streams: seed sets are per-episode and the episode identity sets are disjoint,
so no stream is shared. Row-identity-level leakage across splits was **not**
re-measured in this phase (see §14) — it is structurally impossible because the
V2 row identity binds `episode_id` and `split`, and the episode sets are
disjoint, but the direct row-level check needs the target.

## 6. Validation adequacy gate (C6) — **PASS**

Gate authority: `docs/RVT_RECOVERABILITY_LABEL_AUDIT_GATES.md` gate 4 —
"validation contains at least 30 events from every primary family used for
checkpoint selection". Primary families **F1–F10**, from the H1 requirement
map's `required_families`. Unit: **retained validation source-event pair** — not
rows, not aggregates, not replicas.

| family | retained events | ≥30 |
|---|---:|:--:|
| F1 | 147 | ✓ |
| F2 | 128 | ✓ |
| F3 | 111 | ✓ |
| **F4** | **77** | ✓ |
| F5 | 146 | ✓ |
| F6 | 131 | ✓ |
| F7 | 147 | ✓ |
| F8 | 147 | ✓ |
| F9 | 138 | ✓ |
| F10 | 113 | ✓ |

Minimum family **F4 at 77**, margin **+47**, ratio **2.57×**. The ten per-family
counts sum to 1,285 = the retained pair events.

**This is the gate that failed under V1** — `phase9d_training_readiness_v1.json`
records `RECOVERABILITY_TRAINING_BLOCKED`, blocking gate
`RVT_RECOVERABILITY_LABEL_AUDIT_GATES_GATE_4`, with only F7 passing and F3/F4 at
**zero**. It is the gate the V2 acquisition redesign was authorised to address,
and it now passes for all ten.

## 7. Family × N (C5)

Complete 50-cell matrices for both splits are in
`phase9d_v2c_family_n_matrix_v1.json`. Cell classification is **identical**
across the two splits:

| classification | TRAIN | VALIDATION |
|---|---:|---:|
| `NORMAL_MIXED_LABEL` | 34 | 34 |
| `LEGITIMATE_ONE_CLASS_REGION` | 15 | 15 |
| `EXPECTED_STRUCTURAL_SOURCE_EMPTY` | 1 | 1 |
| `UNEXPECTED_STRUCTURAL_EMPTY` | **0** | **0** |
| `UNEXPECTED_LABEL_DEGENERACY` | **0** | **0** |

Exact structural replication at cell level across disjoint layouts. No threshold
was invented: a cell is one-class if it produced events but only one label class,
and no frozen authority requires both classes per cell.

The per-cell COMPACT/LINE split is not committed at cell granularity and was not
measured here; per-**family** per-topology counts are complete (§9).

## 8. F4/N16 (C7) — `EXPECTED_STRUCTURAL_SOURCE_EMPTY`

| | source episodes | M=0 | eligible states | selected events | rows |
|---|---:|---:|---:|---:|---:|
| TRAIN | 24 | **24** | 0 | 0 | 0 |
| VALIDATION | 6 | **6** | 0 | 0 | 0 |

Present in both splits, and **prospectively predicted in Phase 9D-H1R before any
official V2 row existed**. Not replenished, not treated as ordinary missing data.

**It blocks no frozen H1 claim.** H1 is a pooled paired-episode claim over the
required families; the frozen dataset gate is per-**family**, and F4 reaches 77
from its remaining four N cells. No authority requires every family × N cell to
be non-empty, and the anti-concentration gate constrains where pooled gain may
come from — an empty cell cannot contribute gain. (H5's N=24 question is a
separate sealed domain and was not touched.)

## 9. Zero-positive replication (C8/C16)

| family | TRAIN C+/C− | TRAIN L+/L− | VAL C+/C− | VAL L+/L− |
|---|---|---|---|---|
| F1 | 539/54 | 328/265 | 135/12 | 79/68 |
| F2 | 42/455 | 206/291 | 34/94 | 51/77 |
| **F3** | **0**/423 | **0**/423 | **0**/111 | **0**/111 |
| **F4** | **0**/324 | **0**/324 | **0**/77 | **0**/77 |
| F5 | 260/296 | 73/483 | 87/59 | 28/118 |
| **F6** | **0**/519 | **0**/519 | **0**/131 | **0**/131 |
| F7 | 471/113 | 395/189 | 119/28 | 100/47 |
| F8 | 401/166 | 50/517 | 104/43 | 22/125 |
| F9 | 55/475 | 254/276 | 14/124 | 80/58 |
| F10 | **0**/439 | 94/345 | **0**/113 | 47/66 |

**F3, F4 and F6 are zero-positive on both candidate topologies in both splits** —
exact structural replication on fully disjoint layouts. **F10/COMPACT** is also
zero-positive in both splits while F10/LINE is not: a one-class *candidate*
region, not a one-class family.

Largest per-family-per-candidate rate difference: **F10/LINE 0.2018**, then
**F2/COMPACT 0.1811**. These are recorded descriptively — the frozen gate 8 is a
*pooled* candidate-rate gate and no per-family threshold is predeclared. I am not
inventing one.

## 10. Scenario authority (C9) — the decisive section

### The question

`expected_headroom_categories` declares `LINE_ONLY_SUCCESS` for F3 and F4, and
`COMPACT_ONLY_SUCCESS`/`BOTH_SUCCESS` for F6. The Recoverability labels are
zero-positive for all three. Is that a specification conflict?

### Answer: two distinct objects share the vocabulary — and on the shared question the measured authorities already agree

**Object 1 — `SCENARIO_HEADROOM_CATEGORY`.** Unit: a **layout × team-size cell**.
Declared by `ScenarioFamily.expected_headroom_categories` (per-family design
declaration) and `ScenarioLayout.diagnostic_headroom_by_team_size` /
`headroom_for(team_size)` (per-cell generated declaration), both in
`rvt_swarm/phase8/scenario.py`. `docs/RVT_FD24_SCENARIO_HEADROOM_PROTOCOL.md`
defines it as "always LINE succeeds and always COMPACT fails", assigned "by
frozen diagnostic policies before model training", where success means "the
complete task-level recoverability conditions". The family contract states
qualification "uses always COMPACT, always LINE and the frozen scripted
COMPACT/LINE transition oracle" — i.e. **fixed topology held for the whole
episode from the nominal initial condition**. Bound to **H2**, whose frozen
wording is scoped to "predeclared families with genuine topology headroom".

**Object 2 — `JOINT_RECOVERABILITY_OUTCOME_CATEGORY`.** Unit: **one decision
event**. Computed by `joint_outcome_category(compact_target, line_target)` in
`rvt_swarm/phase8/targets.py` and `_joint_category` in
`rvt_swarm/phase9g0r/producer.py` from the two Target V4 aggregate labels at one
realized decision state. Bound to **H1**; this is what label-audit gate 2 counts.

Against the offered interpretations: **A** for the headroom object, **C** for the
per-family declaration in `scenario.py` (a generator/design target). Explicitly
**not B** — no authority makes a scenario headroom category a decision-state
label expectation.

### The two are not coupled

`grep` for `headroom` across `rvt_swarm/phase9g0r`, `phase9d_h1r`, `phase9b` and
`phase9c` returns **zero** hits in the recoverability generation, acquisition and
compilation path. No authority asserts the two are equal. Their signatures differ:
`headroom_for(team_size)` takes a team size on a layout; `joint_outcome_category`
requires two candidate targets sharing one `decision_event_id`.

### Declared is not measured — and the repository already froze that principle

`tests/test_phase8e_hr_headroom_requalification.py::test_category_follows_outcomes_not_family_name`
is a frozen test. The documented precedent is **F5**: declared
`RECONFIGURATION_REQUIRED`, measured `LINE_ONLY_SUCCESS`, reason "fixed LINE
completes the task, which the frozen definition excludes from
RECONFIGURATION_REQUIRED". The resolution was to **keep the declaration and let
the measurement govern** — the declaration was not rewritten.

### And the measured headroom already says BOTH_FAIL

`headroom_requalification_v6.json`, status **`AUTHORITATIVE_PRE_DATA_HEADROOM`**
(promoted by `headroom_authority_record_v1.json` after a clean detached
reproduction: 150/150 cells re-executed, 450 policy executions, **0 category
mismatches**, full suite 2,587 passed), unit "layout × team-size cell":

| family | declared | v2 (30 cells) | v3 (150) | **v6 (150, authoritative)** |
|---|---|---|---|---|
| F3 | LINE_ONLY_SUCCESS | BOTH_FAIL 3/3 | BOTH_FAIL 12 + INVALID 3 | **BOTH_FAIL 15/15** |
| F4 | LINE_ONLY_SUCCESS | BOTH_FAIL 3/3 | BOTH_FAIL 6 + INVALID 9 | **BOTH_FAIL 12 + INVALID 3** |
| F6 | COMPACT_ONLY / BOTH_SUCCESS | BOTH_FAIL 3/3 | BOTH_FAIL 12 + INVALID 3 | **BOTH_FAIL 15/15** |

**No requalification at any version ever measured a `LINE_ONLY_SUCCESS` cell in
F3 or F4.** The episode-level measured authority already agrees with the
mid-trajectory Recoverability result — and it did so **before any Recoverability
V2 row existed**.

### C10 — decisive conflict test

`RECOVERABILITY_SCENARIO_AUTHORITY_CONFLICT` is **not** returned.

The coexistence argument holds on its own: an episode may carry LINE headroom
from its nominal start and still reach, later on its realized trajectory, states
from which neither candidate completes the task. Frozen authority supports the
distinction because headroom is defined over a fixed policy run from the scenario
start, while the Recoverability label is defined over a candidate commitment from
a realized mid-trajectory state reached under one of six source policies — three
of which (S3, S4, S5) are not fixed-topology.

**But for F3/F4/F6 that argument is not even needed**: the measured episode-level
headroom is BOTH_FAIL, so the two authorities agree directly.

## 11. Hypothesis mapping (C11/C12)

`SCENARIO_FIELD_TO_HYPOTHESIS_BINDING_V1` is in
`phase9d_v2c_scenario_field_hypothesis_binding_v1.json`.

| field | object | primary hypothesis | H1 label gate? |
|---|---|---|:--:|
| `ScenarioFamily.expected_headroom_categories` | layout × N cell | **H2** | no |
| `ScenarioLayout.diagnostic_headroom_by_team_size` | layout × N cell | **H2** | no |
| `joint_outcome_category` / `_joint_category` | decision event | **H1** | **yes** (gate 2) |
| Target V4 candidate aggregate label | candidate at a decision state | **H1** | **yes** |

**`H2_EPISODE_HEADROOM != H1_MID_TRAJECTORY_RECOVERABILITY_LABEL`**, proved on
five axes: different unit, different initial condition, different policy class,
different temporal scope, no shared code path.

### C28 — H2 protection

Nothing was rewritten: 0 scenario declarations changed, 0 geometry changes, 0
headroom category changes. H2's family eligibility comes from the measured
requalification, which this phase leaves untouched: **7 genuine-headroom cells**
(F5 ×1, F9 ×6), `H2_EMPIRICALLY_CONFIRMED = false`, H2 remains falsifiable. H1 is
not being made to pass at H2's expense.

## 12. Target V4 failure decomposition (C13) and positive control (C14)

TRAIN, from the committed frozen replay diagnostic (repository predicate names,
`CandidateReplicaResult.failed_predicates`):

| | F1/COMPACT (control) | F3 | F4 | F6 |
|---|---|---|---|---|
| positives | **20/20** | 0 | 0 | 0 |
| `downstream_goal_complete` failures | 0/20 | **10/10** | **16/16** | **15/15** |
| safety-infeasible replicas | 0/20 | **10/10** | **16/16** | **15/15** |
| termination | GOAL_COMPLETE ×20 | COLLISION ×10 | COLLISION ×16 | COLLISION ×15 |

The **F1 positive control produces positives through the identical frozen code
path**, with `GENERATION_INVALID = 0`. No tuning, no new scientific rows.

**VALIDATION-side predicate decomposition was not measured** (§14). At label
level the replication is exact — F3/F4/F6 zero-positive on both topologies in
both splits — but the mechanism-level comparison the phase asks for is
outstanding.

## 13. Acquisition bias (C15) and decisiveness (C17)

**Acquisition bias ruled out.** TRAIN positive rate by source policy:
S0 0.3147 · S1 0.3157 · S2 0.3124 · S3 0.3106 · S4 0.3065 · S5 0.3296 — spread
0.023. By selection ordinal: 0.3329 · 0.2855 · 0.2920 · 0.3551 · 0.3179 — no
late-ordinal collapse. Per family:

| family | classification |
|---|---|
| F3 | `SCENARIO_STRUCTURALLY_NONRECOVERABLE_AT_SAMPLED_STATES` |
| F4 | `SCENARIO_STRUCTURALLY_NONRECOVERABLE_AT_SAMPLED_STATES` |
| F6 | `SCENARIO_STRUCTURALLY_NONRECOVERABLE_AT_SAMPLED_STATES` |

**Decisive candidate pairs.** These are **observed joint recoverability
categories**, *not* the scenario-manifest categories of the same name — the
schema does not equate them.

TRAIN (complete): `BOTH_FAIL` 2,527 · `BOTH_SUCCESS` 663 ·
`COMPACT_ONLY_SUCCESS` **1,105** · `LINE_ONLY_SUCCESS` **737**.

VALIDATION: four of ten families have a zero-positive candidate, so their joint
distribution is exactly determined from the committed marginals (F3 111 BOTH_FAIL;
F4 77; F6 131; F10 66 BOTH_FAIL + 47 LINE_ONLY). The other six require the
per-event ledger. Exact totals outstanding.

**Informative events exist**: TRAIN alone has 1,842 decisive events, so
candidate-conditioned outcomes genuinely differ and a candidate-conditioned
predictor has signal to learn.

## 14. Predeclared label gates (C18)

All nine from `docs/RVT_RECOVERABILITY_LABEL_AUDIT_GATES.md` (hash matches the
H1 requirement map). **No new gate invented.**

| # | gate | TRAIN | VALIDATION | combined | result |
|---|---|---|---|---|---|
| 1 | each candidate has both classes in train and validation | C 1768/3264, L 1400/3632 | C 493/792, L 407/878 | C 2261/4056, L 1807/4510 | **PASS** |
| 2 | ≥50 train / ≥20 validation events per decisive category | CO 1,105 · LO 737 | CO ≥ **216** · LO ≥ **130** | — | **PASS** |
| 3 | candidate positive rate in [0.10, 0.90] | C 0.3514 · L 0.2782 | C 0.3837 · L 0.3167 | C 0.3579 · L 0.2861 | **PASS** |
| 4 | ≥30 validation events per primary family | — | min F4 = 77 | — | **PASS** |
| 5 | zero N=24 rows in Study A training labels | 0 | 0 | 0 | **PASS** |
| 6 | invalid rollout rate <0.02 overall, <0.05 per family | 0 | 0 | 0.0 | **PASS** |
| 7 | stochastic label instability ≤0.10 per family/candidate | — | — | — | **NOT EVALUATED** |
| 8 | \|train−val\| candidate rate ≤0.15 **and** joint-category JS ≤0.15 | rate C 0.0323 · L 0.0385 → pass | — | JS not computed | **PARTIAL** |
| 9 | event split leakage and duplicate geometry leakage zero | identity 0, layout 0, geometry 0 | — | — | **PARTIAL** |

**Gate 2's validation half is decided rigorously from committed data**, without
the exact joint split: for a family with `E` events, `cp` COMPACT positives and
`lp` LINE positives, `BOTH_SUCCESS ≤ min(cp, lp)`, hence
`COMPACT_ONLY ≥ max(0, cp−lp)` and `LINE_ONLY ≥ max(0, lp−cp)`. Summing gives
**≥216** and **≥130** against a minimum of 20.

**Gate 7 has never been evaluated for V2, in any phase.** Only F8 and F9 run
three replicas; the check needs replica-level data from the target ledgers. This
is the single hardest blocker to verdict C.

## 15. Class balance (C19) and weighting (C20)

Combined: **positive 4,068 · negative 8,566 · total 12,634**, verified. Combined
positive rate 0.3220. Class weighting remains **`NONE_UNWEIGHTED_BCE`** and was
not selected from data. **`NO_POSTHOC_COMBINED_CLASS_BALANCE_GATE_AUTHORIZED`.**

Event-equal weighting, demonstrated numerically on the real combined dataset:

| N | retained events | rows | rows/event | frozen share of weight | naive row-mean share | distortion |
|---|---:|---:|---:|---:|---:|---:|
| 5 | 1,399 | 13,990 | 10 | 0.2215 | 0.1232 | **0.56×** |
| 6 | 1,379 | 16,548 | 12 | 0.2183 | 0.1458 | 0.67× |
| 8 | 1,295 | 20,720 | 16 | 0.2050 | 0.1825 | 0.89× |
| 12 | 1,194 | 28,656 | 24 | 0.1890 | 0.2524 | 1.34× |
| 16 | 1,050 | 33,600 | 32 | 0.1662 | 0.2960 | **1.78×** |

A raw row mean would give one N=16 decision event **3.2×** the scientific weight
of one N=5 event and shift **19.3 %** of total weight from N=5/6/8 to N=12/16.
The frozen reduction — average equally over COMPACT/LINE and robots within a
decision, then over decision events — gives every retained event weight 1.0
regardless of N: per-candidate 0.5, per robot-candidate row 0.5/N (0.1 at N=5,
0.03125 at N=16). No model was trained.

## 16. Feature schema (C22)

TRAIN, fully committed: **node dim 35** on all 90,294 rows, **edge dim 19** on
74,320, 15,974 contract-valid zero-edge graphs, **0 non-finite**, 0 mask
violations, 0 payload validation failures, 0 row-identity failures, one feature
schema hash, `rvt-ego-graph/v2` and `rvt-ego-normalization/v1` throughout,
COMPACT/LINE 45,147/45,147, **no V1/V2 schema mixing**.

VALIDATION: all 23,220 rows were re-validated in-image at generation with **0
failures** across ten checks. The dimension histogram and non-finite scan were
**not** re-measured here, so combined dimension uniformity across both splits is
not yet verified.

## 17. TRAIN vs VALIDATION structure (C23)

Design is uniform in both splits (120/30 episodes per family, 240/60 per N, 200/50
per policy, ratio 4.0). Realized structure:

| | TRAIN | VALIDATION |
|---|---:|---:|
| eligible states / episode | 8.41 | 9.05 |
| selected events / episode | 4.19 | 4.28 |
| rows / retained event | 17.94 | 18.07 |
| M=0 episode fraction | 0.0200 | 0.0200 |
| M<5 fraction | 0.4125 | 0.3833 |
| M≥5 fraction | 0.5675 | 0.5967 |

Pooled label rates differ by 0.0323 (COMPACT) and 0.0385 (LINE) — well inside the
frozen 0.15. Structural categories replicate exactly: same zero-positive
families, same COMPACT-zero-positive set, same structurally empty cell, same cell
classification counts.

**No major structural mismatch.** Two things recorded descriptively: the F10/LINE
(0.2018) and F2/COMPACT (0.1811) per-family shifts, and the N-dependence of label
rates in TRAIN (COMPACT 0.232→0.420 as N grows, LINE 0.397→0.065) — a coherent
chain-length effect present by design in both splits, not a split defect.

Graph-level distributions (node/edge counts, degree) and the VALIDATION
selection-ordinal distribution were not measured.

## 18. Training pipeline (C21) — `TRAINING_PIPELINE_NOT_V2_READY`

Re-audited at `ae45f95`. Only three modules reference the V2 row schema —
`acquisition_v2.py`, `contracts_v2.py`, `producer_v2.py` — and all three are
generation/contract modules, not loaders. `rvt_swarm/phase9c/loader.py` validates
V1-era records and requires grouping fields (`episode_group`,
`decision_event_group`, `layout_group`, `candidate_pair_group`) that V2 rows do
not carry. Training operations: 0. HP trials: 0.

The required additive **`RECOVERABILITY_V2_TRAINING_DATA_LOADER`** must: read the
V2 row schema and validate the 14-field identity; verify all three contract
hashes on every row; group by decision event `(episode_id,
realized_source_timestep)` and never emit a partial event; require both COMPACT
and LINE; require exactly N robot rows per candidate; apply the frozen reduction
and prohibit a raw row mean; emit no class weight, focal term or oversampling;
batch 16 decision-event groups, never flat rows; open exactly one split and
enforce it; refuse V1-schema rows (no mixing); shuffle event groups
deterministically from a declared seed; exclude `GENERATION_INVALID` from the
supervised mask while retaining it as denominator evidence; and fail closed on
N=24, Study-B and final-test identities.

Qualification must include byte-level replay reproducing both committed row
dataset roots, a numeric equal-weight test for an N=5 and an N=16 event,
fail-closed tests for a partial event / missing candidate / wrong robot count,
and a determinism test.

## 19. Model-training contract snapshot (C31) — recorded, not executed

AdamW · LR {1e-4, 3e-4, 1e-3} · weight decay {0, 1e-4} · two frozen loss-weight
tuples `(1.0, 0.5, 0.01, 0.0)` and `(1.0, 1.0, 0.05, 0.0)` · dropout 0.0 · batch
16 decision-event groups + ≤256 grouped action rows · **max 50,000 steps**,
warmup 2,000 · grad clip 1.0 · validate every 1,000 steps · early stop after 8
validations without 0.002 improvement · **max 12 configurations** · **seeds {11,
29, 47}** (seed 0 mechanical dry run only) · DAgger rounds allowed 2, run 0.

Checkpoint selection (`rvt-checkpoint-selection/v1`): every 1,000 steps;
eligibility needs ≥120 closed-loop validation episodes, ≥10 per primary family,
no invalid run, collision-free ≥0.95, degradation ≤0.01; then lexicographic —
collision constraint, task success, Brier, decisive-state ranking accuracy,
transition completion, earlier step. Never selected from training loss. N=24
excluded from Study-A selection.

Execution counters all **0**.

## 20. Validation independence (C24) and sealed domains (C25)

**No contamination.** Zero commits after the VALIDATION closure commit; no
protocol redesign, model selection, training or HP search after seeing VALIDATION
outcomes; only predeclared gates applied; no new gate invented; class weighting
not selected from outcomes. Reading VALIDATION outcomes here is precisely the
role the frozen ordering assigns to a development split. VALIDATION remains
eligible for development and model selection.

Study-A N24 **0** · Study-B **0** · final test **0** · training **0** · HP **0** ·
checkpoints **0** · optimizer states **0** · Residual **0** · V1 mutations **0** ·
V2 TRAIN mutations **0** · V2 VALIDATION mutations **0**. No sealed information
influenced this audit.

## 21. Residual (C32)

**HOLD.** No committed authority states that combined Recoverability adequacy
alone releases Residual V2 before Recoverability model training; every readiness
artifact that mentions it records `residual_v2_authorized = false`. Nothing was
generated.

## 22. Final classifications

**C27 — zero-positive families, one classification each:**

| family | classification |
|---|---|
| **F3** | **A · `LEGITIMATE_STRUCTURAL_ONE_CLASS_REGION_COMPATIBLE_WITH_H1`** |
| **F4** | **A · `LEGITIMATE_STRUCTURAL_ONE_CLASS_REGION_COMPATIBLE_WITH_H1`** |
| **F6** | **A · `LEGITIMATE_STRUCTURAL_ONE_CLASS_REGION_COMPATIBLE_WITH_H1`** |

Incorporating both TRAIN and VALIDATION evidence: measured pre-data headroom
agrees (BOTH_FAIL across all three requalifications); exact independent
replication on disjoint layouts; F1 positive control succeeds through the
identical path; acquisition bias ruled out; no frozen gate violated; zero
`GENERATION_INVALID`. B, C and D are rejected on the evidence above.

**C29 — dataset adequacy finding:**
**`RECOVERABILITY_V2_DATASET_ADEQUATE_WITH_DECLARED_STRUCTURAL_REGIONS`**,
provisional on closing the gate-7, gate-8-divergence and VALIDATION-side
measurements listed below.

**C26 — H1 is scientifically testable on this dataset**, subject to the same
provision.

## 23. What is outstanding

Blocker: the production target `100.71.102.9` became unreachable (SSH and ICMP
both time out) and stayed down for the whole measurement window. **Everything
outstanding is measurement, not analysis**, and two read-only scripts are already
written and staged:

1. **C1** — recompute all 56 shard content hashes and both row dataset roots from
   the sealed row bytes.
2. **C5** — per-cell COMPACT/LINE positive and negative counts, both splits.
3. **C13/C14** — frozen replay failure-predicate decomposition for VALIDATION
   F3/F4/F6 with the F1 positive control.
4. **C17** — exact VALIDATION joint-category counts.
5. **C18 gate 7** — stochastic label instability per family and candidate over the
   F8/F9 three-replica aggregates.
6. **C18 gate 8** — joint-category Jensen-Shannon divergence, TRAIN vs VALIDATION.
7. **C18 gate 9** — row-identity-level leakage check across splits.
8. **C22** — VALIDATION node/edge dimension histograms and non-finite scan.
9. **C23** — VALIDATION graph structural and selection-ordinal distributions.

`scratchpad/v2c_audit.py` covers 1, 2, 4, 7 (partly), 8 and 9;
`scratchpad/v2c_replay.py` covers 3. One detached container run each, read-only
mounts, zero rows written.

---

## Verdict

**E — audit incomplete.**

Not A: the scenario-authority question is resolved, not conflicted — the measured
pre-data headroom authority already records F3/F4/F6 as BOTH_FAIL, and the
repository's frozen principle is that category follows outcomes, not family name.

Not B: no owner scientific decision is outstanding. Every question this phase
raises is answered from frozen authority; what is missing is measurement.

Not C: verdict C asserts adequacy "under **all** frozen criteria". Gate 7 has
never been evaluated for V2, gate 8's divergence component is uncomputed, and
several required recomputations from the actual data were not performed. I will
not claim it.

Not D: no qualified V2 training loader exists.

**Recommendation: `AUDIT_INCOMPLETE`.**

Once the target is reachable, the two staged scripts close every outstanding item.
If they return clean — which the committed evidence gives every reason to expect,
though expectation is not measurement — the verdict becomes **C** and the
recommendation becomes
**`AUTHORIZE_RECOVERABILITY_V2_TRAINING_PIPELINE_IMPLEMENTATION`**, not
`START_MODEL_TRAINING`.

No training, no HP search, no Residual, no N24, no Study-B, no final test.
