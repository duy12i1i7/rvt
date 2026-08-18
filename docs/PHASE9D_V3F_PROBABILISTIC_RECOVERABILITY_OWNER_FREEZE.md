# Phase 9D-V3F — Probabilistic Recoverability V3: Owner Decision and Prospective Freeze

**Verdict A — owner decisions are consistent with repository authority, all V3
scientific contracts and both fresh identity pools are prospectively frozen, V2
history is preserved, and V3 is ready for additive implementation and
qualification.**

**Recommendation: `AUTHORIZE_RECOVERABILITY_V3_IMPLEMENTATION_AND_QUALIFICATION`
— not data generation.**

No V3 episode was executed, no rollout run, no row created, no model trained. V2
was not mutated and gate 7 was not changed.

---

## 1. Owner decisions — 34 recorded, 0 blocking conflicts

All 34 decisions verified against repository authority.
**`H1_OWNER_REWORDING_REQUIRED` was not triggered.**

Two decisions needed more than a rubber stamp:

**Decision 20 (loss).** The frozen loss contract defines `L_rec` as BCE with
logits and no class weighting. The V3 replica-normalized grouped Bernoulli NLL
**reduces exactly to that BCE when R = 1**, so V3 *generalizes* the frozen
contract rather than contradicting it. The R > 1 case is genuinely new and now
carries its own frozen contract.

**Decision 15 (layout offsets).** Compatible, but with a declared consequence —
see §7.

## 2. H1 — preserved without rewording

Three layers, kept separate:

| layer | content | named in H1? |
|---|---|---|
| **scientific claim** | selection improves `EPISODE_TASK_SUCCESS` by ≥0.08 absolute over the direct classifier and the geometric selector, meeting the collision gate, on `PAIRED_EPISODE` units | — |
| **V2 implementation** | all-success binary aggregate over 3 matched replicas | **no** |
| **V3 implementation** | `p(x, τ)` supervised by (k, R) over the same unchanged per-replica Target V4 outcomes | **no** |

Primary metric, evaluation unit, comparator set, 0.08 threshold and collision
gate are all **unchanged**. Only the supervision signal changes.

A **drift tripwire** is recorded: if a future phase makes calibration, NLL or
Brier the *headline* claim rather than a diagnostic, that is hypothesis drift and
must be declared then. This freeze does not do that — Brier enters only where the
frozen checkpoint contract already placed it, at lexicographic position 3 behind
the collision constraint and episode task success.

## 3. The V3 target

**`RECOVERABILITY_PROBABILISTIC_TARGET_V3`**
`a127bf9fbe907c81f2cd8037e94164f738ee756d7480c7db6955d7405bc355b6`

`p(x, τ) = P(Target-V4 outcome = 1 | robot-local state x, candidate topology τ,
frozen disturbance law D) = E_D[Y]`

**Disturbance law** — bound from
`PHASE8E_INITIALIZATION_AND_DISTURBANCE_CONTRACT.md`: uniform on a disk of radius
`0.05·a_max`, additive before the unchanged safety projection, refreshed every
control step, keyed by `(robot_id, control_step, radius|angle)`, iid across
replicas via the counter PRF.

> **Scope limitation, recorded in the contract itself**: `p` is defined *relative
> to this frozen simulation disturbance law only*. No claim is made about any
> real-world disturbance population, and every report using `p` must say so.

**Target V4 is untouched** — `54a0e0ba…` remains the per-replica outcome `Y_r`.
The contract carries an explicit naming rule: *the V3 aggregate is never called
Target V4.*

**Observation is `(k, R)`** — not a binary aggregate, not an abstention label,
not a three-state class, not a hard-thresholded estimate. `k/R` is stored as
descriptive convenience only.

**Mixed outcomes** (`001 010 100 011 101 110`) are `VALID_SUPERVISION` — not
`GENERATION_INVALID`, not discarded, not filtered. `ABSTENTION_TARGET`,
`BOUNDARY_CLASS`, `THREE_STATE_TARGET` are all `NONE`. No runtime threshold `q`
is frozen here.

## 4. Replica protocol

**`RECOVERABILITY_REPLICA_PROTOCOL_V3`**
`6c2143c4782f0d851205cb118a2ff1c3e33c8a6a3e3cdc2ce5a820106551fa9a`

R = 3 for **F8, F9**; R = 1 for the other eight — verified field-by-field against
`replica_count_for_family`, the existing frozen classification. No additional
stochastic families inferred.

`ADAPTIVE_REPLICATION = DISABLED`. No R expansion. Matched COMPACT/LINE streams
required; candidate-specific streams **forbidden**, already enforced by
`_replica_jobs` and by an `OfficialProducerError` guard. CounterStream is
worker-order and retry invariant.

Recorded plainly: **R = 3 is not claimed to estimate any single event's
probability precisely.** Its role is repeated Bernoulli supervision across many
events.

## 5. Row binding and provenance

**`RECOVERABILITY_ROW_BINDING_V3`**
`bdab65bdabbf503dc4d76d7d66d14c6504feb657b32d153a89643fab55058a8c`

Schema `rvt-recoverability-row-identity/v3`, **16 identity fields**, binding all
four contracts: acquisition, Target V4, probabilistic target, replica protocol,
plus the binding hash itself.

**No outcome in identity.** `k`, `R`-derived fractions, labels, dispositions,
worker, retry, path, timestamp, chunk, execution order and `replica_index` are
all on the prohibited list. **R is bound through the replica-protocol hash**, not
recorded as payload — the protocol fixes R per family, so identity determines R
without storing it.

V2/V3 row-id collision is not constructible: different schema string plus two
additional bound hashes. **V2 rows cannot masquerade as V3.**

The supervision record — `(k, R)`, replica labels, dispositions — sits
*alongside*, never inside, any outcome-independent identity.

## 6. Loss and metric

**Loss** `fc9c093327eaaa5ae95c038cf36a2a16ff2fee6d5fdc125dd1106bc3a99dfc11`

`L_candidate = −[k·log p + (R−k)·log(1−p)] / R` — **the division by R is
mandatory**.

| N | R | rows/event | event weight |
|---|---:|---:|---:|
| 5 | 1 | 10 | **1.0** |
| 5 | 3 | 10 | **1.0** |
| 16 | 1 | 32 | **1.0** |
| 16 | 3 | 32 | **1.0** |

*N-invariance*: step 2 averages over the N robots rather than summing, so N = 16
does not receive 32/10 = 3.2× the weight of N = 5.
*R-invariance*: the 1/R factor makes the candidate term a mean per-replica log
likelihood. Without it, F8 and F9 — the **only** multi-replica families — would
be silently up-weighted 3×, inverting the frozen uniform family budget.

**Brier** `0bf6dee325825953d856fb4f6b5df190879424b0d5e8d29cbe55ac930f682f04`
`Brier_candidate = (1/R)·Σ_r (p − Y_r)²`, aggregated robots → candidate → event →
split. Raw row mean is not expressible. Verified against the checkpoint contract:
Brier sits at **lexicographic position 3**, behind the collision constraint and
episode task success — V3 specifies *how* it is aggregated, it does not promote
it.

## 7. Splits — and a capacity finding I did not paper over

**`V3_LAYOUT_SPLIT_REGISTRY_V1`**
`d84d0fb9699dad7d6fe4783d2bd55e1b644ed027948291aeb75148e88ea54dae`

The two authorized offsets are validation-split variants 1 and 2. Each
`(generator_split, variant_index)` pair yields **exactly one layout per family**,
so each offset supplies **10 layouts**.

| | offset | variant | layouts |
|---|---:|---:|---:|
| **V3 TRAIN** | 0.54 | 1 | 10 |
| **V3 VALIDATION** | 0.65 | 2 | 10 |

**Total fresh layout capacity: 20. The split task nominally asked for 20 TRAIN +
10 VALIDATION = 30. Shortfall: 10.**

I did **not** invent a mapping to close that gap. The cleanest deterministic
assignment from the two authorized variants is 10/10 — which is also the owner's
stated preference, and it is compatible with generator semantics.

**Declared consequence**: V3 TRAIN carries **10** layouts where V2 TRAIN carried
**20**; episodes per TRAIN layout rise from 60 to 120. This does **not** affect
the held-out property — V3 VALIDATION keeps its own disjoint 10-layout pool.

**Owner option, recorded but not exercised**: train-split variants 2 and 3
(offsets **0.22** and **0.33**) are unused, sit far below the V2 validation
offset 0.43 and far from the final-test offset 0.79. Authorizing either would
restore 20 TRAIN layouts. Neither is authorized; neither was used.

**Naming hazard, recorded**: V3 TRAIN layouts carry generator-namespace ids of
the form `validation-fN-01`. `layout_id` must **never** be used to infer the V3
dataset split — every manifest entry carries an explicit `v3_split` field.

Frozen V2 scenario code was **not** edited; the registry is additive and
references the unchanged generator.

## 8. Frozen identity pools — both, before any generation

| | episodes | layouts | episodes/layout | event cap | R=3 episodes |
|---|---:|---:|---:|---:|---:|
| **V3 TRAIN** | 1,200 | 10 | 120 | 6,000 | 240 |
| **V3 VALIDATION** | 300 | 10 | 30 | 1,500 | 60 |

Both cover F1–F10, N = {5, 6, 8, 12, 16}, all six source policies. Caps are not
targets; no replenishment, no outcome-dependent stopping. N = 24 absent.

Manifest roots: TRAIN `a4f4b015…`, VALIDATION `004b808c…`.

## 9. Disjointness — 19 axes, all zero

Checked across identity, `episode_id` and `layout_sha256` for: V3 TRAIN vs V3
VALIDATION, each against V2 TRAIN and V2 VALIDATION, and both against the V2
comprehensive development exclusion union (design pilots, V2Q/V2I/V2I-RC/V2QR
canaries).

**Every one of the 19 axes returns overlap 0.**

**`V3_COMPREHENSIVE_DEVELOPMENT_EXCLUSION_UNION_V1`** — **1,880 identities**;
V3 TRAIN ∩ union = **0**, V3 VALIDATION ∩ union = **0**, TRAIN ∩ VALIDATION =
**0**.

**Final domain**: 0 identities inspected, not enumerated. Proof is by the
existing guards — `generate_layouts` raises `PermissionError` for `final_test`
and `derive_seed` refuses final-test derivation — plus geometric separation
(0.54 and 0.65 against the final-test base 0.79). No final identity was revealed.

*A correction worth stating*: my first disjointness pass compared
`l.geometry_sha256` without calling it, so it was comparing bound methods and
would have reported "disjoint" vacuously. Caught and redone with real hashes; the
conclusion held, but only the second pass actually verified it.

## 10. Compute plan (caps only, no generation)

From measured V2 timing — 5.281 CPU-s per replica execution, 2.742 CPU-s per
source episode:

| | replica rollout cap | CPU-h | wall @ 12 workers |
|---|---:|---:|---:|
| V3 TRAIN | 16,800 | 25.56 | 2.13 h |
| V3 VALIDATION | 4,200 | 6.39 | 0.53 h |
| **combined** | **21,000** | **31.95** | **2.66 h** |

These assume every episode yields the maximum K = 5 events, so they are **upper
bounds** containing no outcome-dependent estimate. Rows do not scale with R.

## 11. Gates

**Historical gate 7 is preserved exactly**: `FAILED_FOR_V2`, observed
**59/530 = 0.11132075471698113** against a permitted 0.10. For V3 it is
`NOT_APPLICABLE_TO_V3_PROBABILISTIC_TARGET` — **not** passed, **not** threshold-changed,
**not** erased. Retiring it for V3 is not the same as passing it for V2.

The forbidden gate — *maximum stochastic disagreement ≤ 0.10* — is **not carried
over**, because mixed outcomes are now expected signal.

**Data integrity (D1–D10)**: identity collisions, same-ID conflicts, fake
invalids, partial pairs, replica accounting, matched streams 100 %, replay
mismatches, NaN/Inf, hash recomputation, sealed split overlap — all threshold 0
or exact.

**Scientific adequacy (S1–S8)**: family coverage, candidate coverage,
source-event coverage, **validation ≥30 retained pairs per primary family**
(carried from frozen gate 4), nondegeneracy, split independence, invalid rollout
rate (frozen gate 6), and **S7 — both Target-V4 replica outcomes {0,1} must occur
in the pooled stochastic TRAIN domain**. S7 is explicitly *not* a minimum
mixed-event percentage and is *not* derived from any V2 number.

**Model performance (M1–M5)** is kept separate and applies after training, never
as a data-acceptance gate.

## 12. Data policy

V2 TRAIN and V2 VALIDATION are **`DEVELOPMENT_ONLY`** — neither contributes V3
training loss or V3 validation metrics. No V2 row is relabelled. V3 TRAIN and V3
VALIDATION are fully fresh.

## 13. Next step

Nine additive capabilities specified (I1–I9), including one the V2 run lacked:
**replica-level Target-V4 outcome preservation** — V2 discarded per-replica
records, which is why the gate-7 forensics had to replay to recover them.

Nine-step qualification ladder before any generation: unit tests → **V2 replay
regression** → V3 canary on dedicated identities → replica arithmetic → W1/W12
invariance → candidate-order invariance → failure/resume → local image →
Windows target.

**V3 VALIDATION outcomes must not be inspected** during implementation,
qualification, TRAIN audit, architecture development or HP search. Qualification
uses dedicated canary identities disjoint from both frozen manifests.

## 14. Sealed domains

Study-A N24 **0** · Study-B **0** · final test **0** · final identities
enumerated **0** · training **0** · HP trials **0** · V2 mutations **0** · gate-7
modifications **0** · V3 rows **0** · V3 code implemented **0**.

Full suite: **0 failures**, 90 new tests, including the preserved pin that
`59/530 > 0.10`.

---

## Final verdict

**A** — owner decisions are scientifically consistent with repository authority,
all V3 scientific contracts and both fresh TRAIN/VALIDATION identity pools are
prospectively frozen with an exhaustive disjointness proof, V2 history including
the gate-7 failure is preserved unchanged, and V3 is ready for additive
implementation and qualification.

**Recommendation: `AUTHORIZE_RECOVERABILITY_V3_IMPLEMENTATION_AND_QUALIFICATION`.
NOT data generation.**

Do not generate V3 data. Do not train. Do not run HP search. Do not modify V2. Do
not change historical gate 7. Do not access N24, Study-B or the final test.
