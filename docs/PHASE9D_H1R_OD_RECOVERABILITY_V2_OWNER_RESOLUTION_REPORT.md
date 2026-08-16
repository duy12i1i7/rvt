# Phase 9D-H1R-OD — Recoverability V2 Owner Resolution and Final Freeze

**Result: the sampling ambiguity is prospectively resolved and Protocol V2 is
frozen. Verdict C · AUTHORIZE_FRESH_RECOVERABILITY_V2_GENERATION.**

The owner superseded the historical 70/30 sampling clause for Recoverability V2.
That resolution changed the *authority record only*: the executable selection
semantics of the frozen protocol are provably byte-identical to the H1R design
object. Every primary family clears the unchanged ≥30 gate, the source-episode
budget is untouched, and the two H1R test failures are now proven
**TOOL_ENVIRONMENT_ONLY** — the suite passes completely in the repository's own
qualified environment.

| item | value |
|---|---|
| starting H1R commit | `22159b13283974a5fd6f34eba91f88544e141bf2` (verified present) |
| R2 causal audit | `92668d29c5ea765fc9c1c3ecea23fdc60200b5e6` |
| branch | `research/rvt-phase9d-h1r-recoverability-protocol-v2-v1` |
| **frozen V2 protocol SHA256** | **`19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d`** |

---

## 1. Historical conflict

**The exact clause**, `docs/RVT_DECISION_STATE_SAMPLING_PROTOCOL.md` line 13
(file sha256 `593bdb46…`, matching `phase9d_h1_requirement_map_v1.json`
`authorities.sampling`):

> Sampling is 70% event-balanced and 30% trajectory-uniform.

**Why "event-balanced" was underdefined.** It has no executable definition
anywhere in the frozen tree. V1 never operationalized it — the realized generator
used fixed fractions of the *nominal* family horizon (0.10/0.30/0.50/0.70/0.90),
which is a trajectory-uniform rule on a planned horizon, not a 70/30 mixture.
`results/rvt_fd24/datasets/phase9_generation_budget.json` had already recorded
`BLOCKED_PROTOCOL_INCOMPLETENESS` with
`decision_event_episode_layout_seed_timestamp_mapping` listed as a missing
required declaration — the incompleteness was known and unresolved.

**Why candidate-outcome balancing is prohibited.** The only reading the same
document supports — balancing *decisive*, *both-success* and *both-fail* states —
requires COMPACT/LINE candidate outcomes. Using a candidate outcome to choose
which source states to sample violates the frozen candidate-blind acquisition
requirement and makes sampling circular: the label would determine its own
sampling frame. No post-hoc meaning was invented.

---

## 2. Owner resolution

| item | value |
|---|---|
| old clause status | **SUPERSEDED_FOR_RECOVERABILITY_V2** |
| scope | Recoverability source-state acquisition only |
| new V2 rule | `REALIZED_TRAJECTORY_UNIFORM_K` |
| K | **5** (a cap, never a quota) |
| formula | `idx_j = floor(j · (M − 1) / 4)`, j = 0…4 |
| `M = 0` | zero events, never fabricated |
| `1 ≤ M ≤ 5` | every realized eligible state |
| `M > 5` | exactly 5, first and last always included |
| adaptive replacement | prohibited |
| recorded as | `V2_PROTOCOL_AMENDMENT`, not disguised as the original V1 rule |

Prospective: it lands after V1 was classified pilot/design-diagnostic and before
any fresh V2 TRAIN, V2 VALIDATION, Study-A N24, Study-B, final test or training.

**The resolution changed no executable semantics.** `selection_semantics()`
extracts the 19 rule-bearing keys from both protocol objects and they compare
equal:

```
design protocol object sha256  f2ef1791f2374899250b64fe9b0de39e8c194df5d9951fa818b08bc55bacb77e
FROZEN protocol object sha256  19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d
selection_semantics(design) == selection_semantics(frozen)   →  True
```

The hashes differ only because the frozen object additionally carries the
supersession record, the owner-decision block and the H1-unchanged declaration.
Official V2 generation binds to `19fa68a3…`.

Also frozen: a nonexistent/unreached future source state is
`NOT_A_REALIZED_SOURCE_STATE`, **never** `GENERATION_INVALID`. That disposition
now requires an actually attempted candidate rollout from an existing selected
snapshot. An `M = 0` episode contributes 0 events, 0 fake events and 0 fake
candidate invalids.

---

## 3. H1

> **H1:** *Recoverability selection improves episode task success by at least 0.08
> absolute over both direct classification and local geometric selection, while
> meeting the frozen collision gate.*

Primary unit **PAIRED_EPISODE**, primary metric **EPISODE_TASK_SUCCESS**,
`per_family_effect_claim_predeclared: false`.

**Proof the meaning is unchanged.** The amendment changes only *where along a
realized source trajectory* candidate-blind Recoverability examples are sampled.
It changes none of: candidate topology, Recoverability definition, Target V4,
success/failure definition, evaluation metric, baseline definition, paired
comparison, candidate rollout, candidate-pair atomicity, matched randomness,
F8/F9 three-replica all-success aggregation, safety, class weighting, adequacy
gate. H1 contains no per-stage, per-position or per-family component, and the
decision-state slots are committed as *data sampling times*
(`source_event_timing_addendum_v1.json`), not semantic stages.

Recorded explicitly: `H1_MEANING_UNCHANGED = true`,
`SOURCE_ACQUISITION_V2_PROSPECTIVELY_AMENDED = true`.

---

## 4. V1 data

Pilot / design-diagnostic only. Not merged into V2 confirmatory data, not
mutated, not deleted; manifests and seals preserved permanently.

| root | sha256 |
|---|---|
| TRAIN manifest | `4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf` |
| VALIDATION manifest | `c991aa3016b38b524a14d9b7037b63d97c2cbbb7d92279fc5a297b9c55d4989e` |
| combined Recoverability root | `7e583ef98184767edfb95387ecc23d2ab266e2137db28a9fbb3badccaa495672` |

All three verified unchanged at this commit.

---

## 5. Feasibility requalification

Reused the committed H1R source-only evidence
(`phase9d_h1r_source_only_feasibility_v1.json`, `a37f78ac…`). **No new
outcome-informed search was run. K was not tuned.**

The pilot used 30 episodes per family — exactly the official validation density
(300 ÷ 10), so the projection is direct rather than extrapolated.

| family | episodes | M=0 | M<5 | M≥5 | selected V2 states | projected retained validation events |
|---|---:|---:|---:|---:|---:|---:|
| F1 | 30 | 0 | 1 | 29 | 148 | 88.8 |
| F2 | 30 | 0 | 12 | 18 | 130 | 78.0 |
| F3 | 30 | 0 | 22 | 8 | 102 | 61.2 |
| **F4** | 30 | 6 | 22 | 2 | **80** | **48.0** |
| F5 | 30 | 0 | 4 | 26 | 142 | 85.2 |
| F6 | 30 | 0 | 17 | 13 | 128 | 76.8 |
| F7 | 30 | 0 | 1 | 29 | 148 | 88.8 |
| F8 | 30 | 0 | 6 | 24 | 142 | 85.2 |
| F9 | 30 | 0 | 13 | 17 | 132 | 79.2 |
| F10 | 30 | 0 | 24 | 6 | 106 | 63.6 |

N coverage {5, 6, 8, 12, 16}, six source policies, F1–F10. **All ten families
have nonzero realized source-state support. Families below the gate: none.**
Worst family **F4 at 48.0 against the ≥30 gate — margin 1.60×** (retention
assumption 0.60, carried unchanged from H1R; V1 measured 1.00 given realization).

One structurally empty cell remains: **F4 at N=16 fails initialization validity
under all six source policies**, so it contributes zero states under every
acquisition rule. That is a scenario property, not an acquisition property, and
F4 still clears the gate without it.

---

## 6. Budget

Confirmed from committed authority `results/rvt_fd24/datasets/generation_budget_v1.json`
— **not** accepted from the prompt:

| split | source episodes | frozen decision-event cap | K=5 maximum selected |
|---|---:|---:|---:|
| train | **1,200** | 6,000 | **6,000** |
| validation | **300** | 1,500 | **1,500** |

K = 5 **saturates the frozen event caps exactly**, so a V2 manifest can never
exceed the frozen event budget. Actual selected counts will be lower wherever
`M < 5`, and that is valid: no replenishment, no extra episodes because an
episode yielded few states, no "generate until 30 labels", no "generate until
class balance is good", no "generate until a family reaches a target". The
manifest is fixed prospectively and `compile_v2_source_manifest` rejects any
episode count other than the frozen budget.

---

## 7. Tests

**Canonical invocation recovered** from `docker/generation/Dockerfile` — the
repository's own qualified environment:

```
PYTHONPATH=/opt/rvt   WORKDIR /opt/rvt   PYTHONHASHSEED=0
OMP_NUM_THREADS=1  MKL_NUM_THREADS=1  MKL_CBWR=COMPATIBLE
OPENBLAS_NUM_THREADS=1  NUMEXPR_NUM_THREADS=1
RVT_FD24_NUMERICAL_EXECUTION_PROFILE=FD24_NUMERICAL_EXECUTION_PROFILE_V1
CMD ["python", "-m", "pytest", "-q"]
```

with `docker/generation/run-tests.sh` copying the tree to a writable temp dir
first.

| run | passed | failed |
|---|---:|---:|
| H1R commit, **no** PYTHONPATH (the H1R report's environment) | 3,251 | 2 |
| H1R commit, **qualified environment** | **3,253** | **0** |
| after Phase 9D-H1R-OD, qualified environment | **3,311** | **0** |

Focused tests: **139 passing** across acquisition semantics (M=0, M<5, M=5, M>5,
formula, first/last inclusion, no fabrication, ≤K), candidate blindness,
determinism, worker/order invariance, design-pilot exclusion, V1/V2 identity
separation, outcome-free acquisition preimage, fixed-budget manifest compilation,
and the N24 / Study-B / final-test seals. Of these, **58 are new in this phase**.

**Classification of the H1R failures: TOOL_ENVIRONMENT_ONLY.** Both
`test_command_resolve_binds_manifest_and_narrow_authorization` and
`test_a1v_runner_resolves_exact_empty_validation_boundary` spawn a script as a
subprocess; the subprocess needs `rvt_swarm` importable, which the Dockerfile
provides via `PYTHONPATH`. Running pytest without it made the subprocess fail
with `ModuleNotFoundError`. Setting `PYTHONPATH` reproduces the qualified
environment and both pass. **No `setup.py`/`pyproject.toml` was added, no import
semantics were altered, and no scientific runtime code was changed** — the
repository was never defective. Baseline equivalence evidence: the same commit
yields 3,253 passed / 0 failed under the qualified environment, matching the
completely-passing suite the R2 phase reported.

No test was weakened, modified or deleted; every change in this phase is a new
file plus additive functions in the H1R package.

---

## 8. Provenance

| artifact | sha256 |
|---|---|
| H1R design protocol artifact | `a339279e989ce9200b93ffe33ef4216acbccf34df81d71dcef4259b66af90d4e` |
| H1R design protocol **object** | `f2ef1791f2374899250b64fe9b0de39e8c194df5d9951fa818b08bc55bacb77e` |
| H1R feasibility | `a37f78ac779405817904aca190ad71eea13b36955ef968ae0175cd9927e69570` |
| H1R rule comparison | `a3694a3ba176aa667c6cb807d1cd6369eee650120be50e0adcfb981becb7d37f` |
| H1R design-pilot exclusion set | `ccf88d2f48e8c90ab7be7a6471066778faebd3aeac69dff6575551f48e7117a2` |
| H1R budget design | `c72bea0bcd196d2cd0b5bde93f86b8218227f5cd1b2363edf49c669951f65136` |
| H1R readiness v1 (verdict A, preserved) | `4933095d8a687b452d4bfacf131d29ddbd0f2968853c4a688676c413a0a4c9f0` |
| **owner resolution** | `ae7b0bff48bbfd9eb5d6a01bd143ee9695051f06360c9b469f2d0c9399da3b05` |
| **frozen V2 protocol artifact** | `4d196451de3669af098977be6269128f3dc02a2dc3eeec7a148b8b5a6b6f69d2` |
| **frozen V2 protocol object** | `19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d` |
| **feasibility requalification** | `1fb39024d452f389e677595ab44e0cc76d0c48452ac120653f3ec1257bfd3f62` |
| **readiness v2** | `8719f528f365ccfade9655cb33c6f5d260a6c740658e26af9d98e6ff57fd9c63` |

All H1R artifacts are preserved byte-for-byte; this phase is additive only.
Readiness v1 (verdict A) is retained and referenced by readiness v2 rather than
rewritten.

**Design-pilot exclusion** remains active: 300 identities, `ccf88d2f…`, permanent,
and `compile_v2_source_manifest` fails closed on overlap. The design pilot was not
regenerated.

---

## 9. Sealed domains

Study-A N24 accesses **0** · Study-B accesses **0** · final-test accesses **0** ·
training operations **0** · HP trials **0** · checkpoints **0** · optimizer states
**0** · official V2 rows **0** · official V2 candidate rollouts **0** · V1
mutations **0**.

The manifest compiler additionally refuses N=24 episodes, the
`study_a_n24_evaluation` and `study_b_with_n24` studies, and the `n24_evaluation`
/ `final_test` splits — each as a hard error.

---

## 10. Downstream

Official V2 generation **NO** (not started; requires separate explicit owner
authorization) · Residual V2 **NO** · training **0** · HP search **0** ·
checkpoints **0**.

---

## Verdict

**C — the historical sampling ambiguity is prospectively resolved; Recoverability
Source-Acquisition Protocol V2 is fully frozen, candidate-blind, deterministic,
feasibility-qualified, H1-preserving, and ready for separately authorized fresh
official V2 generation.**

Not A: OD-1 was the only unresolved authority conflict and the owner has resolved
it; the remaining H1R items (OD-2 slot-clause supersession, OD-3 step-0
eligibility, OD-4 F4/N16) are all subsumed by or consistent with this resolution,
and none blocks the freeze.

Not B: selection semantics are byte-identical to the design object and the
amendment touches nothing in the H1 evaluation chain.

Not D: the protocol is frozen with a canonical hash, feasibility is requalified
from committed evidence across F1–F10 and all five nonsealed team sizes, the
budget is confirmed from repository authority, the manifest compiler fails closed,
and the full suite passes 3,311 / 0 in the qualified environment.

**Recommendation: AUTHORIZE_FRESH_RECOVERABILITY_V2_GENERATION**, scoped to fresh
official Recoverability V2 TRAIN and VALIDATION only, bound to acquisition
protocol `19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d`, under
separate explicit owner authorization. Study-A N24, Study B, final test, Residual
V2 and training remain unauthorized.
