# Phase 9G-V2Q — Recoverability V2 Executable / Production Qualification

**Result: the V2 *science* qualifies cleanly, but the V2 *executable path does not
exist in production*. Verdict D · DO_NOT_AUTHORIZE_OFFICIAL_GENERATION.**

The frozen Recoverability Source-Acquisition Protocol V2 is implemented, tested
and byte-identical to its committed artifact — and the qualification canary
exercised it end-to-end through real COMPACT/LINE counterfactuals, Target V4,
aggregation, pair reconciliation and 2·N publication with zero defects. But
**no production module references it.** The official generation path still
compiles V1 nominal-horizon events and still assigns `GENERATION_INVALID` to
source states that never existed — the exact failure Phase 9D-R2 diagnosed. Two
further blockers (the qualified image can no longer be rebuilt, and the target
host is unreachable) prevent completing Q3–Q5, Q15, Q18 and Q20.

---

## 1. Identity

| item | value |
|---|---|
| source / handoff commit | `6098615b354b2f3b6d41e41e3d4beb8d4c5a4694` — verified present, tree clean |
| qualification branch | `research/rvt-phase9g-v2q-production-qualification-v1` |
| Docker image digest | **none — image could not be built (§4)** |
| target host | `100.71.102.9` — reachable by ICMP, **not accessible** (§4) |

All five handoff hashes were re-verified from repository artifacts, not trusted
from prose: owner resolution `ae7b0bff…`, frozen protocol artifact `4d196451…`,
feasibility requalification `1fb39024…`, readiness v2 `8719f528…`, and the frozen
protocol object `19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d`.
Each self-hash validates and each matches the prompt.

---

## 2. Protocol

| item | value |
|---|---|
| V2 protocol SHA256 | `19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d` |
| rule | `REALIZED_TRAJECTORY_UNIFORM_K` |
| K | 5 |
| formula | `idx_j = floor(j·(M−1)/4)`, j = 0…4 |
| candidate blind | yes — selection is a pure function of M and K |

**The executable object equals the committed artifact byte-for-byte.**
`frozen_acquisition_protocol_v2()` re-hashes to `19fa68a3…`, and its
selection-semantics subset is identical to the H1R design object. The frozen
protocol conforms to itself; the problem is that nothing in production calls it.

---

## 3. The blocking finding — V2 is not bound to the executable path

Three findings, all recorded in `phase9g_v2q_executable_binding_gap_v1.json` and
each pinned by a test asserting it against live source.

**V2Q-F1 — the production compiler still schedules V1 events.**
`rvt_swarm/phase9g0r/compiler.py:compile_recoverability_tasks` builds every
`OfficialDecisionEventTask` from `manifest["decision_event_jobs"]`, each carrying
a precomputed `resolved_control_step` read from the frozen **V1** job manifest
`801fe4e2…`. Those are the nominal-horizon slots (0.10/0.30/0.50/0.70/0.90 × H)
that R2 proved unreachable. Official generation launched today would reproduce
the V1 acquisition failure exactly.

**V2Q-F2 — the production producer still invents `GENERATION_INVALID`.**
`rvt_swarm/phase9g0r/producer.py:247`: when
`session.termination is not None and session.control_step < task.resolved_control_step`,
the candidate result is emitted with disposition `GENERATION_INVALID` and
`source_terminated_before_event = true`. This directly contradicts the frozen
owner resolution, which requires a never-realized state to be
`NOT_A_REALIZED_SOURCE_STATE` and never a candidate-stage invalid.

**V2Q-F3 — the row identity cannot bind the V2 protocol hash.**
`RECOVERABILITY_ROW_IDENTITY_FIELDS` has thirteen fields, none for a
source-acquisition protocol hash, and `recoverability_scientific_row_id` rejects
any extra field. **Q14 cannot be satisfied.** A V2 row and a V1 row for the same
realized coordinate would carry the same scientific row identity, so V1/V2
separation would rest on namespace discipline alone.

**Grep result: production modules referencing `phase9d_h1r` = 0.**

None of this is undefined science and none requires a science change — the
science is frozen and complete. It is implementation work, and Q2 forbids me
from improvising it. What must be built before official V2:

1. a V2 decision-event compiler that enumerates the realized universe per source
   episode and applies `REALIZED_TRAJECTORY_UNIFORM_K` with K=5;
2. a producer that consumes a V2-selected realized state instead of re-running
   the source to a scheduled step;
3. removal of the unreached-state `GENERATION_INVALID` branch from the V2 path;
4. an owner-approved **additive** row/event binding carrying the V2 protocol hash.

---

## 4. Image qualification and target host — both blocked

**The qualified image can no longer be rebuilt.** Building
`docker/generation/Dockerfile` for `linux/amd64` at the exact source commit fails
at line 25, exit code 100:

```
E: Version '20230311+deb12u1~deb11u1' for 'ca-certificates' was not found
```

The base-image digest still resolves, and `build-essential=12.9` and
`git=1:2.30.2-1+deb11u5` are still available — but `ca-certificates` has been
superseded in the mutable `bullseye-security` suite, which now offers
`20250419~deb12u1~deb11u1`. The Dockerfile pins exact apt versions against a
moving suite, so the qualified environment is no longer reproducible from its own
definition. Classification: **operational reproducibility defect, zero scientific
impact.**

I did **not** relax the pin, re-pin it, or switch to `snapshot.debian.org` — all
of those would change the repository-authoritative qualified environment that
Q2/Q3 require. I also did not reuse an older image, which Q3 explicitly forbids.
Consequently Q4 (reference suite inside the image) and Q5 (target suite) could
not run.

**The target host is not accessible.** `100.71.102.9` answers ICMP and has port
22 open, and it appears in `known_hosts`, but no `~/.ssh/config` entry maps to it
and key authentication is refused for every plausible account (`aselab`, `asela`,
`aselab5060`, `udy`, `duy`) — the server offers `publickey,password,keyboard-interactive`.
This prompt supplied no credential, and I do not enter passwords. So Q5, the
target half of Q15, and Q20 target measurement did not run. Everything reported
below was measured on the reference host.

---

## 5. Source canary (Q7/Q8)

50 non-official canary episodes, **F1–F10 × N∈{5, 6, 8, 12, 16}**, in a fresh
permanently-excluded namespace (`study_a_qualification_canary` /
`qualification_canary`, seed triple disjoint from both official and design-pilot
seeds). No N=24, no Study B, no final test.

| metric | value |
|---|---|
| episodes | 50 |
| M — min / median / max | 0 / 4 / 11 |
| episodes with M = 0 | 1 |
| selected source states | 201 |
| **fabricated states** | **0** |
| all Q8 invariants pass | **yes, 50/50** |

Per episode the harness checked, rather than assumed: `M=0` → zero events; `M≤5`
→ every eligible state; `M>5` → the exact floor-index formula; first and last
always included; no duplicates; never more than K; every selected index inside
the realized universe; and the frozen 1.5 s minimum spacing preserved.

---

## 6. Candidate canary (Q10–Q13)

10 episodes carrying the whole nonsealed N domain, all selected events, through
the real frozen candidate science — `execute_candidate_pair`, Target V4,
`all_success` aggregation, and the production `reconcile_candidate_pair`.

| metric | value |
|---|---|
| events | 41 |
| candidate aggregates attempted | 82 |
| replica rollouts | 118 |
| **actual `GENERATION_INVALID`** | **0** |
| positive aggregates | 26 |
| valid-negative aggregates | 56 |
| labelable pairs | 41 / 41 |
| rows published | **722** |
| **partial publications** | **0** |
| duplicate row IDs | 0 |

Row counts are exactly 2·N per event in every family — F1 N=5 → 50, F5 N=16 →
160, F9 N=12 → 96, and so on, summing to 722. No partial candidate publication
and no partial robot publication occurred, and nothing was written to any
official namespace.

**Replicas (Q11).** F8 and F9 used exactly **3** replicas per candidate; every
other family used exactly **1**. Verified per event, not per family declaration.

**`GENERATION_INVALID` semantics (Q12).** Zero aggregates were generation-invalid,
and structurally none could be: under V2 selection every candidate rollout starts
from a state that demonstrably exists. The regression against the V1 accounting
failure is pinned by tests that assert the forbidden branch still lives in the V1
producer (V2Q-F2) and that the V2 path cannot reach it.

---

## 7. Determinism (Q9/Q16/Q17)

| check | result |
|---|---|
| selection finalized before any candidate executed | yes |
| selection digest unchanged after all candidates ran | **identical** |
| candidate execution order reversed (LINE-first) | **no scientific change** |
| W=1 vs W=12 semantic digest | **identical** |
| reversed submission order | **identical** |

All three Stage-A digests — W=12, W=1, reverse-order — are the same value. Q15's
reference-vs-target comparison could not run.

---

## 8. Timeout (Q19)

Reference infrastructure timeout **243 s, unchanged**. Maximum observed candidate
pair wall time **36.54 s — 15.0 % utilization**, no exceedance. Timeouts
misclassified as a scientific outcome: **0**. Measured on the reference host, so
this is indicative only until the target runs.

---

## 9. Performance and cost projection (Q20/Q21)

Reference host only; **the target host was not measured**.

| quantity | value |
|---|---|
| source universe construction, mean / max | 1.757 s / 13.35 s per episode |
| selection overhead, mean | 6.8 µs per episode (negligible) |
| candidate pair, mean / max | 6.43 s / 36.54 s |

**Estimates** for official V2 (H1R committed yield 4.1933 events/episode ×
reference-host timing — explicitly not target-measured):

| | TRAIN | VALIDATION |
|---|---:|---:|
| source episodes (fixed) | 1,200 | 300 |
| projected selected events | 5,032 | 1,258 |
| projected candidate aggregates | 10,064 | 2,516 |
| projected CPU-hours | ~9.0 | — |
| projected wall at W=12 | ~0.75 h | — |

No source budget was altered by throughput.

---

## 10. Dry official manifests (Q22/Q23/Q24)

Compiled, never executed; zero candidate results materialized.

| split | source episodes | frozen budget | max selected events | frozen cap | saturates |
|---|---:|---:|---:|---:|---|
| train | **1,200** | 1,200 | 6,000 | 6,000 | yes |
| validation | **300** | 300 | 1,500 | 1,500 | yes |

Both compile at exactly the frozen budget from the real source-episode universe,
bound to protocol `19fa68a3…`, with F1–F10 and N∈{5,6,8,12,16}. N=24 episodes 0,
Study B 0, final test 0, duplicates 0, design-pilot/canary overlap 0, V1 rows
reused 0. **Validation generation remains impermissible** pending TRAIN closure
(Q24).

This validates the *source-episode* manifest only. The official **event**
universe still cannot be produced — that is V2Q-F1.

---

## 11. Tests (Q26)

| run | result |
|---|---|
| focused V2Q qualification tests | **33 passed / 0 failed** |
| full suite, qualified environment (reference) | **3,344 passed / 0 failed** |
| full suite inside the qualified image | **not run — image unbuildable** |
| full suite on the target host | **not run — target unreachable** |

Canonical invocation from `docker/generation/Dockerfile`: `PYTHONPATH=/opt/rvt`,
`WORKDIR /opt/rvt`, `PYTHONHASHSEED=0`, thread caps, numerical profile. No test
was weakened; every change in this phase is a new file.

---

## 12. Closed scopes (Q27)

Official Recoverability V2 rows **0** · V2 TRAIN runs **0** · V2 VALIDATION runs
**0** · Residual V2 **0** · training **0** · HP trials **0** · checkpoints **0** ·
optimizer states **0** · Study-A N24 accesses **0** · Study-B accesses **0** ·
final-test accesses **0** · V1 mutations **0** (roots `4ac3d2cb…` and `c991aa30…`
verified unchanged).

All qualification identities are permanently excluded in
`phase9g_v2q_qualification_canary_exclusion_set_v1.json`, additive to the design-pilot
set and disjoint from it.

---

## Verdict

**D — qualification remains operationally incomplete.**

Not A: no scientific specification problem was exposed. The V2 science is frozen,
complete and internally consistent; the canary exercised it without a single
scientific defect.

Not B: this is not an implemented-but-divergent V2. The V2 acquisition module
conforms exactly to the frozen protocol. There is simply **no V2 implementation
in the production path at all** — and one cannot qualify what has not been built.
(Had the phase9g0r producer been offered as the V2 implementation, V2Q-F2 would
make B the correct verdict.)

Not C: the executable V2 path does not exist end-to-end (V2Q-F1/F2/F3), the
qualified image cannot be rebuilt, and the target host was never exercised — so
none of "production-qualified on the exact target image", reference-vs-target
invariance, or target performance was established.

What *was* qualified, and is solid: candidate-blind realized-state acquisition
across F1–F10 and all five nonsealed team sizes with zero fabricated states; the
real candidate science from V2-selected snapshots with 0 generation-invalid, 0
partial publications and exact 2·N publication; the F8/F9 three-replica rule; and
determinism across W=1/W=12 and execution order.

**Recommendation: DO_NOT_AUTHORIZE_OFFICIAL_GENERATION.**
