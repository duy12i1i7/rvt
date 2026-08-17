# Phase 9D-V2T — Official Recoverability V2 TRAIN Dataset Audit

**Result: the dataset is scientifically adequate with three explicitly documented
one-class families and one structurally empty cell. Verdict C ·
AUTHORIZE_OFFICIAL_RECOVERABILITY_V2_VALIDATION.**

Integrity is exact, all frozen TRAIN-applicable label gates pass, the schema is
clean on all 90,294 rows, and future VALIDATION split hygiene is clean. Two things
need saying plainly: **no V2 training loader exists yet** (`TRAINING_PIPELINE_NOT_V2_READY`),
and **F3/F4/F6 are genuinely one-class regions**, which I established by evidence
rather than assumption.

---

## 1. Dataset identity

| item | value |
|---|---|
| manifest root | `6be6785cef93964b7a2ded21e36a0ae2738dee1e9bc8dfc11715e49516979114` |
| Stage-A root | `06a4b428b26241dcb536dfc11bb9edaecbf699ed2a3441fadb98fbb3b115cb02` |
| candidate root | `ea1f92b79f0c88cea41847d5e82dbf62c4f842af7d6092dd131b430d943dc50b` |
| pair root | `0ca651b133ac95e338faa4849031d62cac173675b011115eb664bd0841771fcb` |
| row dataset root | `c91414f52543d2b0b40c4349000072e1674fc948454e63810ea7d3a66a6287a9` |
| dataset manifest | `cbb8906c75311c53dd203501542ee3a9a77f84e9e92391c27997dee0c4229ef6` |
| **composite TRAIN seal** | **`a966f318832fb60bd99acdfdff72f0c7011d730f3e0fb51494ce318210f39bba`** |
| protocol V2 | `19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d` |
| Row Binding V2 | `98f18a94c6a69d27a4cbf38169ca15e998ce4b4adfbba9a48cb1b3233391adf8` |
| Target V4 | `54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee` |
| image / commit | `sha256:2949628f…` / `f0a923f57fd8bea6b8249fad9652fcd37c674740` |

### One defect found and repaired — in the repository copy, not the data

`phase9g_v2a_t_official_train_dataset_manifest_v1.json` failed its self-hash. Cause:
in the previous phase **I appended a `shard_storage` annotation to the repo copy
after the hash was computed**, without re-attaching it. The on-target manifest
self-verifies at `cbb8906c…`, and the repo copy was identical apart from that one
added key. This is a wrapper bookkeeping error of mine, **not**
`SEALED_DATASET_INTEGRITY_FAILURE`. The repo copy is now byte-identical to the
sealed manifest and the storage note lives in the audit artifacts instead.

## 2. Integrity (D0)

| check | result |
|---|---|
| shards matching manifest | **44 / 44** |
| row dataset root recomputed | matches declared |
| rows streamed | 90,294 |
| duplicate row IDs | 0 |
| duplicates with conflicting payload | 0 |
| row identity validation failures | **0** |

## 3. Accounting (D1)

```
1200 source episodes → 10,096 eligible states → 5,032 selected events
     → 10,064 candidate aggregates (= 2 × 5,032) → 5,032 retained pairs → 90,294 rows
```

Rows equal the **exact per-event Σ 2·N** over retained events (90,294 = 90,294); no
average N was used. Dispositions: 3,168 positive + 6,896 valid-negative = 10,064,
with `GENERATION_INVALID = 0` and **no other disposition present**.

## 4. Effective scientific units (D2)

90,294 rows are **not** 90,294 independent observations. Frozen authority
(`phase9d_recoverability_statistical_unit_v1.json`) sets
`robot_local_rows_statistically_independent = false` and `raw_row_mean_permitted = false`.

| level | count |
|---|---:|
| source episodes | 1,200 |
| **selected source events** (effective unit) | **5,032** |
| candidate aggregates | 10,064 |
| replica executions | 14,452 |
| retained pair events | 5,032 |
| robot-local rows | 90,294 |

Nesting: robots ⊂ candidate topology ⊂ source event ⊂ source episode ⊂ layout/split.

## 5. Event-equal weighting (D3)

Frozen: `FROZEN_EVENT_EQUAL_WEIGHT`, reduction "average equally over COMPACT/LINE and
robots within a decision, then over decision events", `NONE_UNWEIGHTED_BCE`.

| | N=5 | N=16 |
|---|---:|---:|
| rows per event | 10 | 32 |
| frozen event weight | **1.0** | **1.0** |
| per-candidate weight | 0.5 | 0.5 |
| per-robot-row weight | 0.1 | 0.03125 |
| naive row-mean relative weight | 1.0 | **3.2** |

The frozen rule equalises events; a naive row mean would over-weight an N=16 event
by 3.2×.

**`TRAINING_PIPELINE_NOT_V2_READY`.** No module reads
`rvt-recoverability-scientific-row/v2`; `rvt_swarm/dataset.py` and `train.py` are the
older FD24 pipeline, and the frozen artifact itself records "Training has not
started; any future loader/loss must preserve decision-event grouping". This is a
**pipeline gap, not a dataset defect** — the data carries `episode_id` and
`realized_source_timestep`, so decision-event grouping is fully recoverable. An
additive V2 loader is required before training; no data was modified.

## 6. Coverage (D4, D9–D11)

120 source episodes per family and 240 per N — both verified. Cell classification
over the 50 family × N cells:

| classification | cells |
|---|---:|
| BOTH_CLASSES_PRESENT | 34 |
| LABEL_ONE_SIDED_CELL | 15 |
| STRUCTURALLY_EMPTY_SOURCE_CELL | **1** (F4/N16) |
| MISSING_UNEXPECTEDLY | **0** |

Source policies are near-uniform (each 200 episodes; 792–893 events, positives
500–562) — no policy dominates. Rows grow with N (11,150 at N=5 → 26,624 at N=16)
purely because rows = 2·N; this **never enters event weighting**.

## 7. Labels (D7, D12)

| candidate | positive | negative | positive rate |
|---|---:|---:|---:|
| COMPACT | 1,768 | 3,264 | 0.351 |
| LINE | 1,400 | 3,632 | 0.278 |

Joint categories: BOTH_FAIL 2,527 · BOTH_SUCCESS 663 · **COMPACT_ONLY_SUCCESS 1,105**
· **LINE_ONLY_SUCCESS 737**.

Frozen label-audit gates applicable to TRAIN:

| gate | requirement | result |
|---|---|---|
| 1 | each candidate has both classes | **PASS** |
| 2 | ≥50 train events per decisive category | **PASS** (1,105 / 737) |
| 3 | candidate positive rate in [0.10, 0.90] | **PASS** (0.351 / 0.278) |
| 4 | ≥30 retained **VALIDATION** events per family | not a TRAIN gate — see §12 |

No class weights were selected. **NO_POSTHOC_LABEL_BALANCE_GATE_AUTHORIZED** beyond
these frozen gates.

## 8. Selection ordinal (D8)

| ordinal | events | families | N values | positive | negative |
|---|---:|---:|---:|---:|---:|
| 0 | 1,176 | 10 | 5 | 783 | 1,569 |
| 1 | 1,170 | 10 | 5 | 668 | 1,672 |
| 2 | 1,108 | 10 | 5 | 647 | 1,569 |
| 3 | 897 | 10 | 5 | 637 | 1,157 |
| 4 | 681 | 10 | 5 | 433 | 929 |

Counts decline monotonically because episodes with `M < 5` have **absent** ordinals,
not failed events — 1,176 = 1,200 − 24 (`M = 0`). Positive rate is essentially flat
(0.33 → 0.32), so no ordinal is over-represented by scheduling and label outcome is
not driven by trajectory position.

## 9. Zero-positive families — F3, F4, F6 (D6, D27)

The most important audit here. All three are negative on **both** topologies across
423 / 324 / 519 events. I did not accept that at face value; I ran a frozen replay
diagnostic with **F1 as a positive control**.

| cell | replicas | safety-infeasible | `downstream_goal_complete` failures | terminations |
|---|---:|---:|---:|---|
| **F1/COMPACT (control)** | 20 | 0 | **0** | GOAL_COMPLETE 20 → **20/20 positive** |
| F1/LINE (control) | 20 | 15 | 2 | GOAL_COMPLETE 18, COLLISION 2 → 14 positive |
| F3/COMPACT | 10 | 10 | **10 / 10** | COLLISION 10 |
| F3/LINE | 10 | 10 | **10 / 10** | COLLISION 10 |
| F4/COMPACT | 16 | 16 | **16 / 16** | COLLISION 16 |
| F4/LINE | 16 | 16 | **16 / 16** | COLLISION 16 |
| F6/COMPACT | 15 | 15 | **15 / 15** | COLLISION 11, HORIZON 4 |
| F6/LINE | 15 | 15 | **15 / 15** | COLLISION 9, HORIZON 6 |

**Classification for F3, F4 and F6: `SCENARIO_STRUCTURALLY_NONRECOVERABLE`.**

Ruled out by evidence, not intuition:

- **not `SOURCE_ACQUISITION_BIAS`** — V1, using a completely different acquisition
  rule (fixed 0.1H slots), *independently* produced zero positives for F3 (0/14) and
  F6 (0/64); and the V2 positive rate is flat across selection ordinals.
- **not `LABEL_IMPLEMENTATION_DEFECT`** — the F1 control yields 20/20 COMPACT
  positives through the identical frozen code path, and `GENERATION_INVALID = 0`.
- **not `INSUFFICIENT_COVERAGE`** — 423/324/519 events spanning all five N, all six
  source policies and all five ordinals.

**A tension I am flagging rather than smoothing over.** The scenario manifest declares
`expected_headroom_categories` of `LINE_ONLY_SUCCESS` for F3 and F4, and
`COMPACT_ONLY_SUCCESS`/`BOTH_SUCCESS` for F6 — none of which materialised. The
reconciliation is that headroom describes *episode-level* feasibility from the start
under a fixed topology, whereas recoverability requires completing the task from a
**realized mid-trajectory decision state**. V2 samples uniformly across the whole
realized trajectory, and in these passage families **100 % of sampled replicas were
already safety-infeasible at the decision state**. The scenarios are recoverable from
their start; they are not recoverable from where V2 legitimately samples them. That is
real scientific content of the dataset, and it is the kind of thing the combined
TRAIN+VALIDATION adequacy audit should weigh.

## 10. F4/N16 structural empty cell (D5)

All 24 `M = 0` episodes are F4/N16 — the cell contributes 0 events, 0 candidates,
0 rows, and was not replenished. **`EXPECTED_STRUCTURAL_SOURCE_EMPTY`**: the Phase
9D-H1R design pilot recorded this *prospectively*, before official TRAIN, as
`structurally_empty_cells: [{family: F4, team_size: 16, termination:
INITIALIZATION_INVALID}]`. It was predicted, not discovered post-hoc and excused.

## 11. Schema (D14, D15)

| check | result |
|---|---|
| row schema | `rvt-recoverability-scientific-row/v2` × 90,294 |
| ego graph schema | `rvt-ego-graph/v2` × 90,294 |
| node feature dim | **35** on all 90,294 (frozen = 35) |
| edge feature dim | **19** on all 74,320 rows that have edges (frozen = 19) |
| rows with zero edges | 15,974 — contract-valid isolated ego graphs |
| non-finite values | **0** |
| payload validation failures | **0** |
| mask length violations | **0** |
| feature-schema hashes / normalization versions | 1 / 1 |
| candidate topology split | 45,147 COMPACT / 45,147 LINE |
| unit-norm orientation rows | 90,294 / 90,294 |
| V1 schema mixing | none |

**Robot-level consistency (D13):** all 10,064 (event, candidate) groups contain
exactly N rows — 0 violations.

## 12. V1/V2 separation (D16) and future VALIDATION hygiene (D17, D18)

V1 roots verified unchanged; 0 V1 rows in the V2 dataset; row-ID collision is
impossible (different schema string, `realized_source_timestep` instead of
`timestep`, plus two extra bound hashes).

**Source-episode reuse is authorised; row/event reuse did not occur.** The frozen
`generation_budget_v1.json` fixes the 1,200/300 budget and the owner resolution
changed acquisition, not the budget.

**Future VALIDATION hygiene: CLEAN.** I checked whether any authority requires *fresh
validation identities* — none does. Across every committed artifact "fresh" means
freshly generated **rows**; H1R explicitly selected
`KEEP_FROZEN_VALIDATION_EPISODE_BUDGET` and projected feasibility against exactly
those 300 episodes. Independence is preserved because the V2 rule was designed on a
separate, permanently excluded 300-episode design pilot and is provably
candidate-blind; V1 validation outcomes informed the *diagnosis*, not the choice of
K or the rule.

TRAIN vs prospective VALIDATION leakage — **zero on every dimension**:

| dimension | overlap |
|---|---:|
| episode identity | 0 |
| episode_id | 0 |
| layout_sha256 | **0** (20 train layouts vs 10 validation layouts) |
| layout_id | 0 |
| seed tuples | 0 |
| VALIDATION ∩ exclusion union | 0 |

The prospective V2 VALIDATION manifest (`80b13351…`) compiles at 300 episodes /
1,500 max events, binds all three contract hashes, covers F1–F10 and N{5,6,8,12,16},
has zero N24/Study-B/final-test, and does not authorize generation.

**D21:** TRAIN support is *not* the VALIDATION gate. Gate 4 counts **retained events**,
not positives, so nothing in TRAIN shows any family structurally incapable of
reaching ≥30 retained validation events — F3/F4/F6 produce plenty of retained events,
just no positives.

## 13. Timeout tail (D22)

| statistic | seconds |
|---|---:|
| median | 4.22 |
| p95 | 63.57 |
| p99 | 139.06 |
| **max** | **207.13** (F2, N=12, 1 replica) |
| events over 243 s | **0** |
| timeout retries / infra retries / unresolved | 0 / 0 / 0 |

**`VALIDATION_OPERATIONAL_LONG_TAIL_WARNING`** — 14.8 % headroom under the unchanged
243 s timeout. No frozen operational requirement is violated and this is not a
scientific failure. The timeout was not changed.

## 14. F8/F9 replicas (D23)

14,452 replica executions reconcile exactly: F8 (567 events) and F9 (530 events) use
3 replicas per candidate, all other families 1.
`2×(567+530)×3 + 2×(5032−567−530)×1 = 6,582 + 7,870 = 14,452` ✓. Replica
multiplication does not enter event weighting.

## 15. Shards (D25)

44 shards, 1,674,191,736 bytes, all row counts / byte sizes / content hashes matching
the manifest, single schema throughout, no incomplete shard. Nothing was rewritten.

## 16. Learnability, structurally (D19)

Both global classes present; both topologies carry label diversity; 5,032 independent
event-level examples; 1,842 decisive events where the two topologies disagree — the
signal a candidate-conditioned model must learn. Labels are deterministic and
reproducible (the replay diagnostic reproduced dispositions exactly). Three of ten
families are one-class regions. No model was trained, no probe fitted, no feature
selection performed.

## 17. H1 compatibility (D20)

> *Recoverability selection improves episode task success by at least 0.08 absolute
> over both direct classification and local geometric selection, while meeting the
> frozen collision gate.*

Primary unit PAIRED_EPISODE; `per_family_effect_claim_predeclared = false`. H1 is
pooled, so zero-positive families do **not** make it untestable — they are
negative-heavy training regions. No per-family positive requirement was invented.

## 18. Closed scopes

VALIDATION execution **0** · Residual **0** · training **0** · HP trials **0** ·
Study-A N24 **0** · Study-B **0** · final test **0** · rows modified **0** · labels
created **0**.

---

## Final classification and verdict

**`TRAIN_DATASET_ADEQUATE_WITH_DECLARED_STRUCTURAL_CELLS`** — adequate under the
frozen gates, with F4/N16 declared structurally empty (predicted pre-TRAIN) and
F3/F4/F6 declared one-class regions with evidence-based classification.

**Verdict C** — official V2 TRAIN is scientifically adequate under frozen criteria
including the documented structural cells; future V2 VALIDATION split/identity policy
is clean and prospectively frozen; the project is ready for separately authorized
official Recoverability V2 VALIDATION generation.

Not A: integrity, schema and identity are exact; no label defect exists — the F1
control proves the label path produces positives.

Not B: validation split hygiene is clean, with zero overlap on every dimension and
authority explicitly supporting the frozen 300-episode budget.

Not D: every audit item D0–D30 is answered from committed artifacts and dataset
contents.

**Recommendation: AUTHORIZE_OFFICIAL_RECOVERABILITY_V2_VALIDATION.**

Two items to carry forward, neither blocking this verdict:

1. **`TRAINING_PIPELINE_NOT_V2_READY`** — an additive V2 loader enforcing
   decision-event grouping and the frozen reduction must exist before training. The
   authoritative ordering (TRAIN audit → VALIDATION → combined audit → training) means
   this is not needed yet.
2. **F3/F4/F6 one-class regions** — legitimate, independently corroborated, but the
   combined TRAIN+VALIDATION adequacy audit should decide whether a pooled H1 claim
   is well-served by a dataset where three of ten families are unrecoverable from
   their realized decision states.

No validation was generated, no model trained, no residual started, and no sealed
domain accessed.
