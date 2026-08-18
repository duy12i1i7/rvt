# Phase 9D-V2G7 — Recoverability V2 Gate-7 Forensic Root-Cause Report

**Root cause: C — `INTRINSIC_STOCHASTIC_BOUNDARY_WITH_VALID_CURRENT_LABELS`.
Verdict: B — the failure is scientifically real; V2 stays blocked for training
and a prospective V3 repair is recommended.**

A full-census forensic replay of all **1,382** three-replica decision events in
both sealed splits — **2,764** candidate aggregates, every per-replica label,
predicate, seed and state hash — reproduced **59/530 = 0.1113207547** exactly and
found **no implementation, randomness, provenance, replay or label defect
anywhere**. The instability is genuine two-sided stochastic boundary behaviour in
F9/LINE, and the 59 mixed aggregates are **valid robust-negative labels** under
the frozen target, not invalid data.

Gate 7 remains **FAILED**. Nothing in this phase changes that.

---

## Q1. Is 59/530 reproduced exactly? — **Yes**

Recomputed independently from per-replica labels, not from the previous summary.
All eight gate-7 cells:

| split | family | candidate | aggregates | all-pos | all-neg | unstable | rate | |
|---|---|---|---:|---:|---:|---:|---:|:--:|
| train | F8 | COMPACT | 567 | 401 | 125 | 41 | 0.0723104056 | pass |
| train | F8 | LINE | 567 | 50 | 482 | 35 | 0.0617283951 | pass |
| train | F9 | COMPACT | 530 | 55 | 475 | 0 | 0.0000000000 | pass |
| **train** | **F9** | **LINE** | **530** | **254** | **217** | **59** | **0.1113207547** | **FAIL** |
| validation | F8 | COMPACT | 147 | 104 | 35 | 8 | 0.0544217687 | pass |
| validation | F8 | LINE | 147 | 22 | 122 | 3 | 0.0204081633 | pass |
| validation | F9 | COMPACT | 138 | 14 | 124 | 0 | 0.0000000000 | pass |
| validation | F9 | LINE | 138 | 80 | 50 | 8 | 0.0579710145 | pass |

Every cell reconciles: all-positive + all-negative + unstable = aggregates.
Maximum **0.1113207547 > 0.10**. No provenance investigation was required.

## Q2. Is Gate 7 prospective and frozen before V2 outcomes? — **Yes**

| event | commit | date |
|---|---|---|
| gate specification | `c17081fe` | 2026-08-03 16:06:24 |
| gate implementation frozen | `0ffa4d42` | 2026-08-16 01:38:25 |
| official V2 TRAIN generated | `904d96d8` | 2026-08-17 10:05:01 |
| official V2 VALIDATION generated | `ae45f954` | 2026-08-17 11:43:19 |

The specification predates the data by **14 days**, the implementation by **32
hours**, and `docs/RVT_RECOVERABILITY_LABEL_AUDIT_GATES.md` has **exactly one
commit in its history** — it has never been modified.

Gate 3 alone carries "or a scientific-scope review explicitly justifies failure".
**Gate 7 carries no escape clause.**

## Q3. Any implementation, randomness or replay defect? — **No**

| check | result |
|---|---|
| COMPACT stream(e,r) ≠ LINE stream(e,r) | **0** of 4,146 replica pairs |
| matched-seed collisions | **0** of 4,146 distinct draws |
| candidate job seeds shared across candidates | **0** |
| events with divergent `initial_clone_hash` across replicas | **0** |
| replica-index dissent bias, max χ²(2 df) | **4.2034** vs 5.991 critical → not significant |
| replay label / disposition mismatches vs sealed ledger | **0 / 0** over 2,764 |
| all-success rule violations | **0** |
| `GENERATION_INVALID` aggregates | **0** |

`CounterStream` is a pure counter-based PRF with no mutable state, so worker
order, scheduling and retry **cannot** affect a draw. The producer itself raises
`OfficialProducerError` if COMPACT and LINE matched seeds ever diverge, and
official generation completed without error.

Per-index positive rates in the failing cell are tightly clustered — 0.5491 /
0.5189 / 0.5415 — with dissent counts 15 / 27 / 17.

**One correction to my own working assumption**: I initially expected one matched
seed per *event* shared by all three replicas. The frozen design actually derives
a separate matched seed per *replica index* (`replica_index` is part of the seed
derivation) and additionally separates replicas by the stream label
`replica-{i}`. COMPACT and LINE share both at the same index. The contract holds
exactly; my expectation was wrong, not the data.

## Q4. Exact 3-replica bit patterns

TRAIN F9/LINE, bit *i* = replica *i*'s label, 1 = success:

| pattern | count | kind |
|---|---:|---|
| 000 | 217 | stable negative |
| 001 | 9 | one-success / two-failure |
| 010 | 8 | one-success / two-failure |
| 100 | 10 | one-success / two-failure |
| 011 | 5 | two-success / one-failure |
| 101 | 19 | two-success / one-failure |
| 110 | 8 | two-success / one-failure |
| 111 | 254 | stable positive |

**27 one-success vs 32 two-success.** Near balanced — this is two-sided boundary
behaviour, not a rare near-miss tail on one side.

TRAIN F9/COMPACT is perfectly bimodal: **475 × `000`, 55 × `111`, zero mixed**.

## Q5. Which Target V4 predicate flips? — **`target_metric_v3_dwell_complete`, in 59/59**

Predicates failing in a negative replica but in **no** positive replica of the
same aggregate:

| predicate | count | fraction |
|---|---:|---:|
| **`target_metric_v3_dwell_complete`** | **59** | **1.000** |
| `downstream_goal_complete` | 50 | 0.847 |
| `safety_projection_resolved` | 50 | 0.847 |
| `collision_free_complete_horizon` | 50 | 0.847 |
| `protocol_resolved` | 50 | 0.847 |
| `candidate_commitment_valid` | 9 | 0.153 |
| `transition_execution_valid` | 9 | 0.153 |

Terminations among unstable replicas: positive replicas always `GOAL_COMPLETE`
(91); negative replicas `COLLISION` (70) or `GOAL_COMPLETE` (16).

**One mechanism dominates.** In every unstable aggregate the final Metric V3
dwell fails in the dissenting replica. In 50 that co-occurs with a collision; in
the remaining 9 the team reaches the goal yet still misses the dwell. This is the
dynamic obstacle disrupting the final formation dwell — not a label-code defect.

## Q6. Why is F9/COMPACT perfectly stable while F9/LINE is not?

**The disturbance reaches COMPACT.** All 530 TRAIN F9/COMPACT aggregates show
three *distinct* replica `final_state_hash` values from one shared
`initial_clone_hash`, and 127 of 530 even differ in control-step count. Across
all 2,764 aggregates in both splits, **2,764 diverge**. The perturbation is
applied everywhere; it simply never flips COMPACT's outcome.

The asymmetry is physical:

| | positive rate | instability |
|---|---:|---:|
| TRAIN F9/COMPACT | 0.1038 (55 vs 475) | 0.0000 |
| TRAIN F9/LINE | 0.4792 (254 vs 217) | 0.1113 |
| VALIDATION F9/COMPACT | 0.1014 | 0.0000 |
| VALIDATION F9/LINE | 0.6014 | 0.0580 |

F9/LINE is the most evenly split cell in the dataset. An elongated LINE chain
also presents more exposed geometry to a moving obstacle and must additionally
complete a topology transition. Stream mismatch does **not** explain it — there
is none.

## Q7. Localized or broadly distributed? — **Broadly distributed, with structure**

| dimension | spread |
|---|---|
| layouts | both TRAIN F9 layouts: 22/261 and 37/269 |
| team size | all five: 0.0417 (N=6) → 0.1939 (N=12) |
| source policy | all six: 0.0444 (S2) → 0.1977 (S1) |
| episodes | 48 of 120 contain at least one |
| selection ordinal | **0.2667 (ord 0) → 0.0000 (ord 4)** |

Unstable events sit **earlier** in the trajectory: mean source-timestep fraction
**0.2478** vs **0.4652** for all F9/LINE events.

Physically coherent: early decision states still face the moving obstacle, so the
outcome genuinely depends on which disturbance realization occurs; later states
are past the contested region and settled. No post-hoc subgroup gate was created.

## Q8. Is the TRAIN/VALIDATION difference explainable? — **Yes**

59/530 = 0.1113 vs 8/138 = 0.0580; absolute difference **0.0533**, ratio 1.92×.
VALIDATION has **one** F9 layout against TRAIN's two and roughly a quarter the
sample, so its estimate is far less precise — its exact 95 % interval
**[0.025357, 0.111030]** reaches the TRAIN point estimate at its upper edge.

The same structure appears in both: F9/COMPACT perfectly stable, instability
concentrated at low ordinals, and no instability at all at N=5 or N=6 in
VALIDATION (the two lowest-rate cells in TRAIN). The splits are consistent, not
in conflict. **VALIDATION passing is not used to override the TRAIN failure.**

## Q9. What does inference say, and why does that not pass the gate?

| cell | observed | exact 95 % CI | one-sided *p* (H₀: p ≤ 0.10) |
|---|---|---|---:|
| TRAIN F9/LINE | 59/530 = 0.1113207547 | [0.085830, 0.141239] | **0.2108** |
| VALIDATION F9/LINE | 8/138 = 0.0579710145 | [0.025357, 0.111030] | 0.9711 |

Clopper-Pearson computed by bisection on the exact binomial CDF — no library
default, no normal approximation, no continuity correction.

The data **are** statistically compatible with an underlying instability
probability of 0.10; H₀ is not rejected.

**This does not pass the gate.** Gate 7 is an *empirical dataset gate* on the
**observed** statistic, not a hypothesis test about an inferred parameter. The
observed value exceeds 0.10, so the gate fails. The inference is context for
prospective design only, and is not used to reopen the verdict.

## Q10. Would more replicas reduce the metric? — **No, they make it strictly worse**

P(disagree) = 1 − p^R − (1−p)^R. Since
d/dR [p^R + (1−p)^R] = p^R ln p + (1−p)^R ln(1−p) < 0 for every p ∈ (0,1),
agreement probability strictly *decreases* in R and disagreement strictly
*increases*.

| p | R=3 | R=5 | R=7 | R=9 |
|---|---:|---:|---:|---:|
| 0.05 | 0.1425 | 0.2262 | 0.3017 | 0.3698 |
| 0.10 | 0.2700 | 0.4095 | 0.5217 | 0.6126 |
| 0.30 | 0.6300 | 0.8295 | 0.9174 | 0.9596 |
| 0.50 | 0.7500 | 0.9375 | 0.9844 | 0.9961 |

"Add more replicas" is **not** a repair for this gate. It is a repair only in
combination with a different target or a different stability statistic.

## Q11. Invalid data, or valid robust negatives? — **Valid robust negatives**

The frozen protocol is explicit:

> Aggregation is **all-success**: every valid replica must meet all V4
> conditions. Mixed outcomes set the instability flag; numerical invalidity sets
> invalid and blocks the row.

Mixed outcomes are an **anticipated, permitted state** of Target V4 — flagged,
not invalidated. Only numerical invalidity blocks a row. Measured across both
splits: all **154** mixed aggregates carry disposition **`VALID_TASK_NEGATIVE`**
and label **0**; **zero** `GENERATION_INVALID` anywhere; **zero** all-success rule
violations.

`unstable = len(set(outcomes)) > 1` is a first-class field on the frozen target
object itself.

## Q12. Is Gate 7 aligned with Target V4's intended meaning?

Target V4's semantics are **`ROBUST_RECOVERABILITY_UNDER_ALL_SAMPLED_DISTURBANCES`** —
not an empirical success-probability proxy (three replicas cannot estimate one,
and the label discards the count) and not a deterministic stress test (the
disturbance is sampled; every aggregate shows three distinct final states).

Target V4 and gate 7 are **complementary, not redundant**: the target resolves an
individual mixed aggregate conservatively, while gate 7 bounds how often that
happens across the population.

There is a real structural tension worth recording: under all-success
aggregation, disagreement frequency is largest exactly where per-event success
probability is furthest from 0 and 1 — the informative decision boundary a
candidate-conditioned predictor most needs to learn. **I record this as a design
consideration for a successor protocol, not as a finding that the frozen gate is
defective, and not as grounds to change it.**

## Q13. Can V2 TRAIN be used for training under frozen V2 rules? — **No**

`BLOCKED_FOR_TRAINING_UNDER_FROZEN_GATE7`. No measurement-invalidating defect was
found, so the gate result stands and the frozen rule — "a failed gate blocks
training" — applies.

Separately, the dataset **is** `SCIENTIFICALLY_INFORMATIVE_FOR_PROTOCOL_DEVELOPMENT`:
all seals and 56 shards verify byte-for-byte, eight of nine gates pass, labels are
valid under the frozen target, and it holds the only measured evidence of where
F9/LINE's stochastic boundary lies. **It must not be deleted.**

## Q14. Can V2 VALIDATION remain confirmatory if the science changes? — **No**

Its outcomes have been inspected repeatedly — dataset adequacy, zero-positive
family diagnosis, gate 7, gate 8, scenario-semantic reconciliation, and this
forensic phase. If the target, gate, scope or eligibility criteria change
*because of* what those inspections showed, V2 VALIDATION is **development
evidence**, not held-out confirmation.

A V3 repair requires **fresh independent validation identities** that were not
used to design V3. Final-test layouts must not be used and none were generated
here.

## Q15. What is the cleanest prospective repair?

**Option E — a prospectively frozen robust binary Target V3 with declared
abstain semantics**, with **option D (calibrated probabilistic target)** as the
scientifically richer but costlier alternative.

Ranked by scientific defensibility:

| rank | option | class | why |
|---|---|---|---|
| 1 | **E** robust binary V3 | CLEAN_PROSPECTIVE_REPAIR | keeps a binary target close to current meaning; gives the ambiguous region *declared* semantics instead of hiding it |
| 2 | **D** probabilistic target | CLEAN_PROSPECTIVE_REPAIR | most faithful to stochastic families; Brier already in the frozen checkpoint contract — but changes loss, metrics, H1 framing, and costs most |
| 3 | C more replicas | mixed | useful only *inside* D or E; alone it provably worsens the failing statistic |
| 4 | A threshold change | POSTHOC_SALVAGE | cheapest, least defensible; the amended threshold would sit just above the observed failure |
| 5 | B exclude F9 / LINE / the 59 | POSTHOC_SALVAGE | outcome-dependent filtering that also guts H2 (F9 holds 6 of 7 measured headroom cells) and destroys candidate-conditioned learning (LINE) |

Dropping the 59 events is legitimate **only** if a new prospectively frozen
target defines such states as abstentions *before* they are observed.

## Data reuse under a V3 repair

| asset | gate interpretation only | target semantics change | replica count change |
|---|---|---|---|
| source episodes | reusable | reusable as identities | reusable |
| Stage-A snapshots | reusable | reusable | reusable |
| graph inputs | reusable | reusable as inputs | reusable |
| candidate rollout replicas | reusable | as evidence, not labels | prefix only, if prospectively authorized |
| **aggregate labels** | reusable | **not reusable** | **not reusable** |
| **robot-local rows** | reusable | **not reusable as labelled rows** | **not reusable as labelled rows** |
| TRAIN split | reusable | reusable after relabelling | reusable after re-execution |
| **VALIDATION split** | reusable | **not reusable as confirmatory** | **not reusable as confirmatory** |

Any semantics or replica-count change requires a new Target contract hash,
rollout configuration hash, row-binding version, row identity version, dataset
namespace, manifest and both seals. **Mixed scientific semantics under one
dataset identity is prohibited.**

## Owner decision package

Four choices, in `phase9d_v2g7_owner_decision_package_v1.json`. I did **not**
select one.

1. **`KEEP_FROZEN_V2_GATE7_AND_REJECT_CURRENT_DATA_FOR_TRAINING`** — strongest
   integrity story; no compute; but H1 Recoverability gets no trained model.
2. **`POSTHOC_AMEND_GATE7`** — *scientifically weaker*. No compute, no
   regeneration, but the threshold would be chosen after seeing the failure, with
   both splits already observed. Must be reported transparently with the original
   failing value.
3. **`PROSPECTIVE_V3_STOCHASTIC_RECOVERABILITY_REPAIR`** — addresses the cause;
   requires regenerating candidate rollouts and all labelled rows, plus fresh
   confirmatory validation identities; highest compute; cleanest publication path.
4. **`OTHER_EVIDENCE_SUPPORTED_REPAIR`** — reserved; **no repository evidence was
   found** for a materially better option.

Binding on all four: the historical V2 gate-7 verdict is FAIL and cannot be
retroactively changed; no choice may be justified by the fact that it makes the
existing dataset pass; final-test evidence must not inform any successor design.

## Integrity of this phase

TRAIN and VALIDATION were mounted **read-only** throughout. Forensic replay wrote
**0** rows into official data, modified **0** manifests and **0** seals. TRAIN 44
shards and VALIDATION 12 shards unchanged; both seals unchanged. Study-A N24 0 ·
Study-B 0 · final test 0 · training 0 · HP 0 · Residual 0 · labels changed 0 ·
rows deleted 0 · families excluded 0 · candidates excluded 0 · gate 7 modified 0 ·
threshold modified 0 · official data regenerated 0.

Full suite: **0 failures**. The existing test pinning the gate-7 failure remains,
and a new explicit guard asserts `59/530 > 0.10`.

---

## Final root-cause classification

**C — `INTRINSIC_STOCHASTIC_BOUNDARY_WITH_VALID_CURRENT_LABELS`**

A, B, D and F are excluded on the evidence above. **E** (gate/semantic
misalignment) is retained only as a *secondary design consideration* for a
successor protocol — this phase does not assert the frozen gate is defective.

## Final verdict

**B — the Gate-7 failure is scientifically real; current V2 remains blocked for
training, and a prospective V3 repair is recommended.**

**Recommendation: option 3, `PROSPECTIVE_V3_STOCHASTIC_RECOVERABILITY_REPAIR`,
preferring variant E.** The phase directs that where evidence shows genuine
stochastic-boundary behaviour with no bug, a prospective scientific repair is
preferred over moving the threshold just above the observed failure. That is
exactly what the evidence shows. I did not perform it; it requires owner
authorization.

V2 is **not** marked PASS. No training, no HP search, no Residual, no N24, no
Study-B, no final test.
