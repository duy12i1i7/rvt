# Phase 9G-V2I — Recoverability V2 Production Implementation

**Result: the V2 executable path is implemented, V1 stays replayable, Row
Identity V2 is frozen, and the production image is reproducible again. Verdict C
· DO_NOT_AUTHORIZE_OFFICIAL_GENERATION.**

All three Phase 9G-V2Q blocking findings are closed additively. The only thing
still outstanding is operational: the target host has no configured key-based
access, so remote requalification remains **TARGET_REQUALIFICATION_PENDING**.

---

## 1. Identity

| item | value |
|---|---|
| start commit | `92ff458772ec0654b88f5985e1ca70bf81c66602` — verified, clean |
| implementation commit | `9c738b75c0975c06ec7648abb15984a4f34d84e0` |
| qualified-image commit | `fc95f13714c63c65701dfba28b520a6787ed909d` |
| branch | `research/rvt-phase9g-v2i-production-implementation-v1` |
| V2 protocol SHA256 | `19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d` |
| Row Binding V2 SHA256 | `98f18a94c6a69d27a4cbf38169ca15e998ce4b4adfbba9a48cb1b3233391adf8` |
| production image | `sha256:4ce3ff6b6a7c59614a09ef2acdd676462fc1174ddd2aef6faeaa0cb34257cc5e` |

All four handoff authority hashes were re-verified from the artifacts before any
code was written.

---

## 2. The V2 executable

Two stages (I6), with Stage A frozen before Stage B begins.

| component | module |
|---|---|
| compiler | `rvt_swarm/phase9g0r/compiler_v2.py` |
| producer | `rvt_swarm/phase9g0r/producer_v2.py` |
| contracts | `rvt_swarm/phase9g0r/contracts_v2.py` |

**Stage A — `execute_v2_source_acquisition`.** Runs the source episode, enumerates
the realized eligible universe on the frozen 1.5 s spacing grid, applies
`REALIZED_TRAJECTORY_UNIFORM_K` with K=5, and returns an immutable
`V2SourceAcquisition` with its own `acquisition_sha256`. No candidate exists at
this point, so candidate blindness is structural rather than conventional.

**Stage B — `compile_recoverability_v2_candidate_tasks` + `produce_recoverability_v2_event`.**
Each selected realized state becomes one `OfficialDecisionEventTask` whose
`resolved_control_step` **is** the realized step. Every task carries the Stage A
source-state fingerprint it came from, and the compiler refuses any task whose
step escapes the realized trajectory.

**Candidate path — reused verbatim.** `produce_recoverability_candidate` is the
existing production function, called unchanged: same snapshot, same graphs, same
Target V4, same replica rules, same aggregation, same `reconcile_candidate_pair`.

**Matched randomness — unchanged.** Seeds still come from the frozen
`derive_generation_seed` PRF, with the selection ordinal in the role V1 gave the
slot index. The matched disturbance seed still omits candidate topology, so
COMPACT and LINE receive the same realization; the per-candidate job seed still
includes it. Verified by test.

**Row publisher.** `producer_v2` builds Row Identity V2 keys and publishes only
through `reconcile_candidate_pair`, preserving 2·N atomicity.

---

## 3. V1 compatibility

Nothing in V1 was modified: not the compiler, not the producer, not the row
identity, not the `GENERATION_INVALID` accounting, not the manifests. Dispatch is
by explicit protocol version, never an ad-hoc flag:

```
produce_recoverability_event_by_protocol(..., protocol_version=RECOVERABILITY_V1 | RECOVERABILITY_V2)
```

Replay tests pin that `produce_recoverability_candidate` still contains the
historical `source_terminated_before_event` branch and that
`RECOVERABILITY_ROW_IDENTITY_FIELDS` is byte-identical to its frozen tuple.

---

## 4. V2 source events

`M` is the count of realized eligible states for one episode. `M = 0` yields zero
source events and zero candidate tasks — normal, not an error, and asserted by
the compiler. `1 ≤ M ≤ 5` retains every state; `M > 5` uses
`idx_j = floor(j·(M−1)/4)`. **No future event ID is ever created and later
resolved.** Canary episodes with `M = 3` produced exactly 3 events, and none
fabricated a fourth or fifth.

---

## 5. Row Identity V2

Owner clause I9, additive, frozen prospectively. Fourteen fields:

```
schema · study · split · family · layout_sha256 · team_size · episode_id
realized_source_timestep · robot_id · candidate_topology_id · graph_fingerprint
target_v4_contract_sha256 · source_acquisition_protocol_sha256
recoverability_row_binding_v2_spec_sha256
```

Prohibited and rejected on sight: label, aggregate label, candidate outcome,
disposition, model output, worker, chunk, attempt, retry, execution order, wall
clock, serialization path, timeout.

**Collision proof (I19).** For identical scientific coordinates:

```
V1 row id  ≠  V2 row id
```

They cannot collide: the schema string differs, V1's `timestep` is replaced by
`realized_source_timestep`, and V2 additionally binds the acquisition protocol
and the V2 binding spec. Conversely, the same V2 record hashed under different
worker, chunk, attempt, retry or key-iteration order yields an **identical**
row id. Graph fingerprint semantics were not touched (I10).

---

## 6. Producer semantics

| situation | V1 | V2 |
|---|---|---|
| source never reached the step | `GENERATION_INVALID` (historical, preserved) | cannot occur; producer raises rather than publishing |
| candidate actually attempted and invalid | `GENERATION_INVALID` | `GENERATION_INVALID` (unchanged contract) |

The I21 regression executes both protocols on the same episode: V1 given an
unreached step returns `source_terminated_before_event = true` with
`GENERATION_INVALID`, while V2's selected steps are all ≤ the terminal step and
the unreached step appears nowhere. **Fake `GENERATION_INVALID` under V2: 0.**

---

## 7. Manifest

| split | source episodes | K=5 maximum | frozen cap |
|---|---:|---:|---:|
| train | **1,200** | 6,000 | 6,000 |
| validation | **300** | 1,500 | 1,500 |

The scientific unit is the **source episode**; realized event counts are
emergent, and the maxima are caps rather than targets. `adaptive_refill_permitted`
and `outcome_dependent_stopping_permitted` are both false. Compilation fails
closed on sealed studies, sealed splits, N=24, duplicates, and any identity in
the design-pilot or qualification-canary exclusion sets (600 identities loaded).
Compiled only — never executed. Validation generation stays impermissible until
TRAIN closes.

---

## 8. Canary

Non-official `study_a_v2i_canary` / `v2i_canary` namespace, seeds shifted off the
official streams, 10 episodes covering F1–F10 across N ∈ {5, 6, 8, 12, 16}.

| metric | value |
|---|---:|
| events | 43 |
| candidate aggregates attempted | 86 |
| rows published | **780** |
| partial publications | **0** |
| duplicate row IDs | **0** |
| actual `GENERATION_INVALID` | 0 |
| **fake `GENERATION_INVALID`** | **0** |
| positive / negative aggregates | 30 / 56 |

Row counts are exactly 2·N per event in every family. Four episodes had `M < 5`
(F3 M=4, F4 M=3, F8 M=3, F10 M=3) and produced exactly `M` events each. F8 and F9
used 3 replicas per candidate; all other families used 1. Row schema was
`rvt-recoverability-scientific-row/v2` throughout.

---

## 9. Determinism

20 canary episodes, Stage A digests:

```
W=12  ==  W=1  ==  reverse order
```

Worker count and scheduling order changed wall time only.

---

## 10. Failure / resume

Stage A is idempotent: two independent runs produced the same
`acquisition_sha256`, the same selected event IDs and the same source-state
fingerprints. Stage B was interrupted after 2 of 5 events, then resumed from a
durable ledger keyed by scientific identity: **2 completed units skipped, 3
resumed, 0 completed units regenerated under a new identity, 0 duplicate rows,
0 partial publications**, pair atomicity preserved. Re-submitting an already
completed unit reproduced byte-identical row IDs and was refused a second ledger
append.

---

## 11. Docker

The pinned `ca-certificates=20230311+deb12u1~deb11u1` had vanished from the live
rolling mirrors. Under owner clause I25 it was recovered **unchanged** from an
immutable Debian snapshot rather than re-pinned:

| item | value |
|---|---|
| snapshot | `20260220T214329Z` (`debian` + `debian-security`) |
| package file | `ca-certificates_20230311+deb12u1~deb11u1_all.deb` |
| sha1 / size | `128f98420f0138f754a27a471985478d17fe5bef` / 168,944 B |
| package versions changed | **0** |
| re-pinned to a newer version | **no** |
| base image | digest-pinned, unchanged |

In-image verification: `build-essential 12.9`, `ca-certificates
20230311+deb12u1~deb11u1`, `git 1:2.30.2-1+deb11u5` — exactly the frozen pins.
The `requirements.lock.txt` was not touched.

Two build-context problems were also found and are worth separating: a stale
macOS `CMakeCache.txt` under `third_party/Python-RVO2/build` was entering the
context and breaking the `pyrvo2` wheel — untracked host dirt, never in git, now
excluded via `.dockerignore` (a clean-checkout image is unchanged by this). And a
build from a git *worktree* fails the Dockerfile's own `git rev-parse HEAD`
assertion, because a worktree's `.git` is a pointer file; the authoritative build
was therefore done from a clean clone.

A third, genuine repository defect surfaced only inside the image:
`tests/test_phase9g_a1v_validation.py` hard-coded `ROOT/.venv/bin/python` — the
only such occurrence in the suite, every other subprocess test uses
`sys.executable`. No `.venv` exists in the production image, so that test could
never run in the canonical environment. It was introduced by commit `6ce4a37`,
not by this phase, and is fixed by using `sys.executable`; nothing it asserts
changed.

**Image**: `sha256:4ce3ff6b6a7c59614a09ef2acdd676462fc1174ddd2aef6faeaa0cb34257cc5e`,
`linux/amd64`, revision label `fc95f137…`, Python 3.9.6, numpy 2.0.2,
torch 2.8.0+cpu, with `PYTHONPATH=/opt/rvt`, `PYTHONHASHSEED=0` and all numeric
thread caps set. An earlier build at `9c738b75…`
(`sha256:da5b98b6…`) is superseded: it predates the a1v `sys.executable` fix. The
only repository change after the qualified-image commit is this document and the
provenance text recording it — no code, test or contract differs.

---

## 12. Tests

| run | result |
|---|---|
| focused V2I | **70 passed / 0 failed** |
| focused V2Q + V2I | **103 passed / 0 failed** |
| full suite, reference, qualified env | **3,414 passed / 0 failed** |
| full suite inside the image | **3,414 passed / 0 failed** |

Two Phase 9G-V2Q tests failed at first — by design. They were tripwires I wrote
last phase to pin the gap: "no production module binds the V2 acquisition
package" and "the Dockerfile was not modified". This phase legitimately inverted
both. They were **updated, not deleted or weakened**: the first now asserts the
binding exists *and* that the historical V2Q finding is preserved unchanged; the
second now asserts every package pin survived the repair byte-identically and
that the recorded before/after hashes match.

---

## 13. Target

**TARGET_REQUALIFICATION_PENDING.** `100.71.102.9` has no configured key-based
access. No password was requested, guessed, embedded or logged, and no credential
appears in any artifact, script or log. Per I28 this is an operational blocker
only: nothing scientific was changed to work around it, and production
qualification is explicitly **not** marked complete.

The reference production profile is unchanged: workers 12, threads 1, chunk 1,
timeout 243 s.

---

## 14. Sealed

Official V2 TRAIN rows **0** · V2 VALIDATION rows **0** · Residual rows **0** ·
training **0** · HP trials **0** · checkpoints **0** · optimizer states **0** ·
Study-A N24 access **0** · Study-B access **0** · final-test access **0** ·
V1 mutations **0**.

---

## Verdict

**C — the V2 production executable is implemented correctly, V1 remains
replayable, Row Identity V2 is frozen, deterministic local and image
qualification passes, and only target-host requalification remains operationally
pending.**

Not A: no new scientific specification was needed. Every frozen contract —
Target V4, K, the selection formula, COMPACT/LINE, matched randomness, replica
rules, aggregation, pair atomicity, 2·N publication — was reused unchanged.

Not B: the executable conforms to the frozen protocol without any science
change; the frozen protocol object is byte-identical to its committed artifact.

Not D: target-host requalification did not happen, so the project is not yet
ready to rerun Phase 9G-V2Q final qualification end to end.

Not E: the implementation is complete — compiler, producer, row identity,
manifest, dispatch, canary, determinism, failure/resume and a reproducible image
all landed and are under test.

**Recommendation: DO_NOT_AUTHORIZE_OFFICIAL_GENERATION.** The next authorization
remains a separate phase, and target access must be configured first.
