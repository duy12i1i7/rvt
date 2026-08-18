# Phase 9D-V3D — Prospective Stochastic Recoverability V3 Design

**Recommendation class C — `PROBABILISTIC_RECOVERABILITY`.
Verdict A — the V3 target is sufficiently specified for an owner decision and
freeze phase. Recommendation: `OWNER_DECISION_AND_FREEZE_RECOVERABILITY_V3`.**

Nothing was implemented, no V3 row was generated, no model was trained, gate 7
was not touched, and V2 remains
`BLOCKED_FOR_TRAINING_UNDER_FROZEN_GATE7` with its failure —
**TRAIN F9/LINE 59/530 = 0.1113207547 against a permitted 0.10** — preserved
verbatim.

The single most important finding is a repository fact, not a modelling
preference: **the F8/F9 replica streams are iid samples from an explicitly
specified probability distribution**, so `p(x, τ)` is the quantity the
experiment already measures.

---

## Q1. What scientific quantity should V3 predict?

**`p(x, τ) = P(task success | robot-local state x, candidate topology τ)`**,
the expectation over the frozen disturbance law:

> Y = task success under the frozen Target contract for one candidate rollout,
> conditioned on the robot-local ego graph, the candidate topology, the realized
> source decision state, the frozen dynamics/controller/safety/transition/metric
> stack, and the disturbance realization D.
> `p(x, τ) = E_D[ Y(x, τ, D) ]`.

## Q2. Genuine samples, or a fixed stress bank? — **Genuine iid samples**

This is decided by authority, not preference:

| evidence | source |
|---|---|
| "uniform disk, max `0.05*a_max`, before safety projection" — a named continuous distribution with bounded support | disturbance contract |
| refreshed "every control step, counter-key independent", keyed by `(robot_id, control_step, radius\|angle)` | disturbance contract |
| `r = r_max·√u_r`, `θ = 2π·u_θ` — the standard inverse-CDF construction for the uniform measure on a disk | `streams.py::uniform_disk` |
| `counter_uniform` = first 64 SHA-256 bits of a canonical payload ÷ 2⁶⁴ — a counter PRF implementing U[0,1) draws | `phase8e/protocol.py` |
| replica index enters via the stream label `robot_acceleration:replica-{i}` and the matched seed | `counterfactual.py`, `compiler_v2.py` |
| the contract **explicitly rejected** stress-bank and candidate-specific-stream alternatives | disturbance contract |

**Conclusion: `POPULATION_PROBABILITY_UNDER_A_FROZEN_DISTURBANCE_LAW`.**
Determinism comes from the counter PRF, not from a fixed sample list — replaying
replica *i* reproduces its draw, while drawing replica *i+1* yields a fresh
independent realization. Both hold at once.

**Necessary caveat, to be repeated in every future report**: `p` is defined
*relative to* the frozen uniform-disk law (0.05·a_max, additive before safety
projection). It is not a claim about any real-world disturbance population.

## Q3. Is R = 3 sufficient? — **Depends entirely on the target**

Exact Clopper-Pearson intervals for k of 3:

| k/3 | point | CI95 | width |
|---|---|---|---:|
| 0/3 | 0.000 | [0.0000, 0.7076] | 0.708 (one-sided only) |
| 1/3 | 0.333 | [0.0084, 0.9057] | **0.897 — uninformative** |
| 2/3 | 0.667 | [0.0943, 0.9916] | **0.897 — uninformative** |
| 3/3 | 1.000 | [0.2924, 1.0000] | 0.708 (one-sided only) |

Replicas needed for a per-event ±half-width at p = 0.5:

| half-width | R |
|---|---:|
| 0.30 | 11 |
| 0.25 | 17 |
| 0.20 | **27** |
| 0.15 | 47 |
| 0.10 | **104** |

**The decisive asymmetry.** Targets that need *per-event* certainty about p
(option D, and any statistically-justified three-state variant) require R ≥ 27 at
every F8/F9 event — prohibitive and still coarse. A **binomial-likelihood target
does not**: k of R is a noisy but *unbiased* observation of `p(x, τ)`, and
consistency comes from the **number of events**, not from R within an event.
Precision that matters lives at the calibration bin, where 100 events give
±0.10 and 200 give ±0.07.

So R = 3 is useless for a single-event estimate and perfectly coherent as
supervision. Raising R buys calibration-bin resolution, not per-event certainty —
that trade-off is recorded, and R remains an **owner parameter**.

## Q4. Delete, abstain, classify, or model the mixed states? — **Model them**

**`RETAINED_AS_PROBABILISTIC_SUPERVISION`.**

- **Not deleted**: the 59 TRAIN F9/LINE events are physically real, carry valid
  labels, and sit exactly where a candidate-conditioned selector has the most to
  learn. Deleting them is outcome-dependent filtering.
- **Not abstain-only**: an abstention head needs supervision, which requires
  keeping the boundary events anyway — so option A collapses into option B once
  made workable. *A design that simply deletes mixed samples cannot teach a
  runtime when to abstain.*
- **Not a discrete boundary class**: defining "boundary" as *mixed replicas*
  makes class membership a function of **R**, since
  `P(mixed) = 1 − p^R − (1−p)^R` increases monotonically in R. A class whose
  membership depends on the sampling budget is not a property of the state.

## Q5–Q6. Which option preserves H1, and which makes the strongest paper?

**H1 is unchanged under every option.** Its exact statement —

> Recoverability selection improves episode task success by at least 0.08
> absolute over both direct classification and local geometric selection, while
> meeting the frozen collision gate.

— specifies a *selection* improving `EPISODE_TASK_SUCCESS` on `PAIRED_EPISODE`
units. It says nothing about the target's internal type. The binary all-success
label is an **implementation choice**, cleanly separable from the hypothesis.

| | A abstain | B three-state | C probabilistic | D LCB |
|---|---|---|---|---|
| H1 literally unchanged | ✓ | ✓ | ✓ | ✓ |
| comparator definition changes | no | no | no | no |
| evaluation metric changes | yes | yes | **no** | no |
| model head changes | yes | yes | yes | no |
| runtime rule changes | yes | yes | yes | yes |
| paper claim | narrower (covered subset only) | different (new class) | **stronger** | similar, two unjustified constants |
| verdict | collapses into B | variant 1 unsound, variant 2 prohibitive | **sound and affordable** | prohibitive and under-specified |

**C gives the strongest paper**, and one detail matters: the frozen checkpoint
selection contract *already* ranks by "minimize recoverability Brier score",
which presupposes a probabilistic output. Option C moves the target **toward**
existing frozen selection authority, not away from it.

## Q7. Can V2 TRAIN be reused? — **Only with new provenance, and there is no reason to**

V2 TRAIN is `DEVELOPMENT_DATA` — used for generation, audit, gate-7 diagnosis and
V3 design.

| asset | A | B | C | D |
|---|---|---|---|---|
| source snapshot | reusable | reusable | reusable | reusable |
| ego graph inputs | reusable | reusable | reusable | reusable |
| **three per-replica outcomes** | evidence | evidence | **reusable as k of R = 3 observations** | insufficient |
| aggregate all-success label | **not reusable** | **not reusable** | **not reusable** | **not reusable** |
| robot-local rows *as labelled rows* | **not reusable** | **not reusable** | **not reusable** | **not reusable** |
| robot-local rows *as input payloads* | reusable | reusable | reusable | reusable |

In-place relabelling is **prohibited**. Any reuse produces a *new* row under a
*new* identity citing the V2 execution as evidence.

**And the compute argument for reuse does not exist.** From measured V2 timing
(19,594 CPU-s over 3,710 replica executions → **5.281 CPU-s/replica**):

| design | replica executions | CPU-hours | wall @ 12 workers |
|---|---:|---:|---:|
| R=3 on F8/F9 (current) | 18,162 | 26.6 | 2.2 h |
| R=5 on F8/F9 | 23,690 | 34.8 | 2.9 h |
| R=9 on F8/F9 | 34,746 | 51.0 | 4.3 h |
| R=3 on all families | 37,902 | 55.6 | 4.6 h |

A complete fresh V3 generation costs about **2.2 hours of wall time**. Compute is
**not** a constraint, so it must not be an argument for reuse. F8/F9 are 22 % of
events but **53 %** of stage-B CPU, so replica increases land on the expensive
families. Rows do **not** scale with R.

## Q8. Why can V2 VALIDATION no longer be confirmatory?

Because its outcomes have been inspected six times — family adequacy, label
balance, zero-positive families, gate 7, gate 8, scenario semantics, and now V3
design. Contamination type: **`OUTCOME_INFORMED_DESIGN`**.

It may still serve as development evidence and model-selection input under a
declared provenance note. It may **never** be described as held-out for a V3
protocol these results helped shape.

## Q9. What new validation domain is required?

New VALIDATION layout identities from currently unused variant indices of the
already-authoritative scenario generator — **no final-test access needed**.

`offset = _SPLIT_OFFSETS[split] + 0.11 × variant_index`, and `offset` directly
parameterises geometry (e.g. F1 `lateral = 3.0 + offset`):

| validation variant | offset | |
|---|---:|---|
| 0 (current) | 0.43 | in use |
| **1** | **0.54** | safely separated |
| **2** | **0.65** | safely separated |
| 3 | 0.76 | **only 0.03 from the final-test base 0.79** |
| 4 | 0.87 | **crosses the final-test offset** |

**Variants 1 and 2 are the safe choices.** Each family's declared parameter range
must be re-checked before freezing. This extends `_SPLIT_VARIANTS` in frozen
scenario code and therefore **requires owner authority** — I have not assumed it.

The pool must be frozen **before** V3 training, outcome-unseen, and
layout-disjoint from V2 TRAIN, V2 VALIDATION and final test.

## Q10. Can the sealed final set remain valid? — **Yes, conditionally**

Zero final-test identities, hashes, outcomes or statistics were inspected;
`generate_layouts` raises `PermissionError` for `final_test` without explicit
authorization, and `derive_seed` carries `sealed_final_authorized`.

It remains valid provided V3 science is designed only from development data
(true here), nothing about it is observed before the frozen final evaluation, its
layout pool is unchanged, and split authority keeps it disjoint. **Caveat**: if
fresh validation variants were pushed to index 3 or beyond, validation geometry
would approach the final-test region and this would need re-examination.

## Q11. What replaces Gate 7?

Historical gate 7 is **not amended** — it failed for V2 and stays failed. It is
**retired for V3 and replaced**, because under a probabilistic target a mixed
replica outcome is no longer a nuisance to bound: an event with k = 1 or 2 is
*precisely* an observation that p is interior. Capping how often that occurs
would cap how much the dataset says about the decision boundary. The statistic is
also R-dependent, so the same physical dataset would fail harder simply for being
sampled more thoroughly.

**Data integrity** — `V3-D1` no identity collisions · `V3-D2` no non-finite
inputs · `V3-D3` exact replica accounting · `V3-D4` no fake invalids ·
`V3-D5` matched randomness, 0 mismatches · **`V3-D6` replay determinism, 0
mismatches** (this inherits the part of gate 7 that was genuinely about
trustworthiness) · `V3-D7` split disjointness.

**Scientific distribution** — `V3-S1` per-family validation minimum (inherits 30)
· `V3-S2` target non-degeneracy *(owner threshold)* · **`V3-S3` stochastic-boundary
representation, expressed as a MINIMUM not a maximum** — the deliberate inversion
of gate 7 · `V3-S4` invalid rollout rate (inherits <0.02 / <0.05) · `V3-S5`
TRAIN/VALIDATION comparability.

**Model performance** — `V3-M1` calibration/ECE *(owner)* · `V3-M2` binomial NLL
and Brier *(owner)* · `V3-M3` decision quality against the **already-frozen** H1
values, 0.08 absolute and the collision gate.

Categories kept strictly separate. **No threshold taken from any V2 observed
value.**

## Q12. What must be frozen before implementation?

Target definition and its contract hash · disturbance interpretation · replica
protocol including R per family and any adaptive rule · source acquisition
protocol (the V2 hash may stand, but must be restated) · eligibility and
retention · candidate aggregation and observation schema · row identity and
binding version · the complete gate set **with every threshold** · TRAIN and
VALIDATION layout pools including new variant indices · budgets · training event
weighting and the 1/R normalization · target weighting · evaluation metrics and
checkpoint selection.

**Event weighting, concretely.** The per-candidate term is
`−(1/R)[k·log p̂ + (R−k)·log(1−p̂)]` — the *mean* per-replica NLL, invariant to R.
Then average over robots within a candidate, then the two candidates, then
events. Without the 1/R factor an R = 9 event would contribute nine times the
gradient of an R = 1 event — and since F8/F9 are the *only* multi-replica
families, that would silently up-weight exactly the two stochastic families,
inverting the frozen uniform family budget.

| N | R | rows/event | per robot-candidate row | effective event weight |
|---|---:|---:|---:|---:|
| 5 | 1 | 10 | 0.1 | **1.0** |
| 5 | 9 | 10 | 0.1 | **1.0** |
| 16 | 1 | 32 | 0.03125 | **1.0** |
| 16 | 9 | 32 | 0.03125 | **1.0** |

## Q13. Recommended path

**Option C, `PROBABILISTIC_RECOVERABILITY`:**

- **object** `p(x, τ)` under the frozen disturbance law
- **observation** k successes out of R matched replicas
- **loss** event-equal grouped binomial NLL, normalized by 1/R
- **runtime** one scalar per candidate; select the larger, hold the committed
  topology within a frozen near-tie margin
- **boundary** retained as probabilistic supervision

**Path shape**: generate fresh V3 TRAIN (affordable), and require fresh
confirmatory VALIDATION regardless of the TRAIN choice.

**Ordering, with two corrections to the proposed sequence.** The fresh
**VALIDATION layout pool must be frozen *before* V3 TRAIN generation**, not
after — the comprehensive exclusion union must know every validation identity
before TRAIN runs, exactly as Phase 9G-V2A-T did when it froze the full
1,500-episode identity space and proved TRAIN ∩ VALIDATION = 0 in advance.
Second, whether the sealed final test precedes Study-A N24 and Study-B is flagged
for owner confirmation rather than resolved here.

## Safety

Recoverability prediction **never** overrides the frozen local safety projection.
Uncertainty may influence *which* candidate is proposed, never whether the safety
constraint is enforced. The safety controller is unmodified. When the prediction
is uncertain or the candidates fall within a frozen margin, the conservative
default is to **hold the committed topology** — an unnecessary transition is
itself a risk.

## Publication

V2 must not be hidden. Report the frozen gate with its prospective freeze date,
the measured **59/530 = 0.1113207547** against 0.10, the forensic diagnosis, the
fact that the V3 target type was chosen from **disturbance semantics rather than
from the failing statistic**, and the fresh confirmatory domain. Label
development evidence and confirmatory evidence distinctly in every table.

A predeclared gate catching a real property of the data is evidence the protocol
**worked**.

## Owner parameters — not selected here

Target semantic type (recommended C) · R_min and whether R rises · adaptive
replication · q and confidence level (option D only) · conservative-default and
near-tie margin · fresh validation size and variant indices · extension of
`_SPLIT_VARIANTS` · V2 TRAIN reuse policy · `V3-S2`, `V3-S3`, `V3-M1`, `V3-M2`
thresholds · H1 rewording *(not required under C)*.

Resolved by repository authority, **not** an owner choice: the replica
interpretation — iid samples from a frozen disturbance law.

**Adaptive replication** is scientifically valid only *conditionally*: the
stopping rule must be frozen beforehand, depend only on observed successes,
enter the aggregate identity, and be taken **jointly for the COMPACT/LINE pair**
— a per-candidate rule would break matched randomness and must be prohibited.
Not recommended for the first freeze; there is no cost pressure to justify the
complexity.

## Residual risks I am flagging

1. `p` is relative to the frozen uniform-disk law, not to any real disturbance
   population.
2. If the evaluation headline drifts from episode task success to calibration,
   that **is** hypothesis drift and must be declared.
3. Deterministic families would carry R = 1, so their observation is degenerate
   at 0 or 1. Whether to raise R there is an owner parameter with real cost.
4. Extending the validation variant space touches frozen scenario code.

---

## Final recommendation class

**C — `PROBABILISTIC_RECOVERABILITY`**

## Final verdict

**A — the prospective V3 scientific target is sufficiently specified and ready
for an explicit owner decision and freeze phase.**

**Recommendation: `OWNER_DECISION_AND_FREEZE_RECOVERABILITY_V3`. Do not implement
yet.**

V2 remains blocked. Gate 7 unchanged. No V3 data generated, no V3 implemented, no
training, no HP search, no N24, no Study-B, no final test.
