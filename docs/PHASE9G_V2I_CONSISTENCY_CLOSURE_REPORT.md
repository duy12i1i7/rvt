# Phase 9G-V2I-RC — Consistency Closure, Hash-Binding Audit, Final Image Freeze

**Result: both provenance ambiguities resolve cleanly. No scientific defect
exists. Verdict C · PROCEED_TO_WINDOWS_TARGET_REQUALIFICATION.**

`98f18a94…` never replaced anything — it is an *additional* provenance hash, and
the frozen scientific protocol `19fa68a3…` is independently and exactly bound in
every V2 identity. The commit/image mismatch was real but narrow: three files, no
code. The final image is rebuilt from the exact closure commit.

---

## The ten questions

**Q1. What is `98f18a94…`?**
The **Recoverability Row Binding V2 contract** hash —
`recoverability_row_binding_v2_spec_sha256`, produced by
`rvt_swarm/phase9g0r/contracts_v2.py::recoverability_row_binding_v2_spec()`. It is
an additive operational-provenance object declaring the V2 row field set, the
prohibited-field set and the I9 owner authorization. It **embeds** the frozen
protocol (`spec["acquisition"]["source_acquisition_protocol_sha256"] = 19fa68a3…`)
and occupies its **own separate field** in the row identity. It is not, and never
substitutes for, the source-acquisition protocol hash.

**Q2. Does Row Identity V2 bind exact `19fa68a3…`?** **Yes**, in the dedicated
field `source_acquisition_protocol_sha256`, alongside `target_v4_contract_sha256`
and `recoverability_row_binding_v2_spec_sha256` as three distinct fields.

**Q3. Does candidate-task provenance bind exact `19fa68a3…`?** **Yes.**
`V2SourceAcquisition.protocol_sha256 == 19fa68a3…`, and each task's `event_id` is
the SHA-256 of a preimage containing that value — verified by recomputing the
event id independently and matching it to `tasks[0].event_id`. Substituting any
other value changes the id.

**Q4. Do future official manifests bind exact `19fa68a3…`?** **Yes**, both TRAIN
(1,200 episodes) and VALIDATION (300 episodes).

**Q5. What changed between `fc95f137…` and `feaf4a8…`?** Three files, 26
insertions, 9 deletions — the phase report and two canonical provenance
artifacts. **Zero** Python runtime, contracts, Dockerfile, dependencies or tests.

**Q6. Was the old image scientifically/executably equivalent?** **Executably yes,
formally no.** Not one byte of runtime, contract, Dockerfile or test differs. But
both changed artifacts are read by qualification tests that run *inside* the
image, so under the acceptability rule the `fc95f137` image is not the final
qualified image.

**Q7. What exact commit is the FINAL image built from?**
`f0a923f57fd8bea6b8249fad9652fcd37c674740` — the Phase 9G-V2I-RC closure commit.

**Q8. What image digest should target qualification use?**
`sha256:2949628f6eb57abafe680687b677958c7cc52bffab84545514a48d84a936c684`.

**Q9. Does the image report that exact commit?** **Yes.** In-image `git rev-parse
HEAD` returns `f0a923f5…`, matching exactly; the Dockerfile also asserts it at
build time.

**Q10. Did full in-image tests pass?** **Yes — 3,427 passed, 0 failed**, identical
to the reference host.

---

## 1. Identity

| item | value |
|---|---|
| handoff commit | `feaf4a8a4bf8ab1522a659b89f0078bd2451ec80` — verified, clean |
| branch | `research/rvt-phase9g-v2i-consistency-closure-v1` |
| frozen protocol | `19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d` |
| row binding V2 | `98f18a94c6a69d27a4cbf38169ca15e998ce4b4adfbba9a48cb1b3233391adf8` |

---

## 2. Hash-role registry

Full values are in `results/rvt_fd24/phase9g_v2i_consistency_closure_v1.json`;
abbreviated here for readability only.

| name | class | role |
|---|---|---|
| `…protocol_v2_FROZEN` `19fa68a3…` | **SCIENTIFIC** | the frozen K=5 acquisition contract |
| `…protocol_v2_DESIGN` `f2ef1791…` | scientific historical | H1R design object, superseded |
| `…row_binding_v2_spec` `98f18a94…` | **operational, additive** | V2 row field set + I9 authorization |
| `target_v4_execution_contract` `54a0e0ba…` | scientific | candidate disposition semantics |
| `owner_sampling_resolution` `ae7b0bff…` | scientific authority | OD-1 supersession record |
| `v2_executable_binding` `147bc6cc…` | canonical artifact | records V2↔production binding |
| `row_identity_v2_contract` `9dcde635…` | canonical artifact | committed Row Identity V2 record |
| `v2_source_manifest_train` / `_validation` | generation runtime | dry-compiled manifest roots |
| `recoverability_row_binding_v1_spec` | scientific historical | V1 row identity, untouched |

---

## 3. Row Identity V2 preimage

```json
{"candidate_topology_id":5,"episode_id":"rvt-generation-job-identity/v1/source_episode/example/episode-0","family":"F3","graph_fingerprint":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","layout_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","realized_source_timestep":60,"recoverability_row_binding_v2_spec_sha256":"98f18a94c6a69d27a4cbf38169ca15e998ce4b4adfbba9a48cb1b3233391adf8","robot_id":2,"schema":"rvt-recoverability-row-identity/v2","source_acquisition_protocol_sha256":"19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d","split":"train","study":"study_a_zero_shot","target_v4_contract_sha256":"54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee","team_size":8}
```

```
row_id = ccd8a64c5ef247f429a446b8e9bd80ca8262d32760113d944ae12e247591b447
```

Both hashes appear, in separate fields, exactly as required. No outcome or
operational field is present — asserted by a test that scans the literal preimage
bytes for `label`, `disposition`, `worker`, `chunk`, `attempt`, `retry`,
`wall_clock`, `model_`, `outcome` and the disposition vocabulary.

---

## 4. Manifest binding

| split | source episodes | binds `19fa68a3…` | executed |
|---|---:|---|---|
| train | **1,200** | yes | no |
| validation | **300** | yes | no |

---

## 5. Commit and image consistency

```
 docs/PHASE9G_V2I_..._IMPLEMENTATION_REPORT.md            | 12 ++++++++----
 results/.../phase9g_v2i_docker_reproducibility_repair_v1.json | 19 ++++++++++++++---
 results/.../phase9g_v2i_next_generation_readiness_v1.json     |  4 ++--
 3 files changed, 26 insertions(+), 9 deletions(-)
```

| path | classification | runtime | read by qualification tests |
|---|---|---|---|
| `docs/…IMPLEMENTATION_REPORT.md` | REPORT_ONLY | no | no |
| `…docker_reproducibility_repair_v1.json` | CANONICAL_ARTIFACT | no | **yes** |
| `…next_generation_readiness_v1.json` | CANONICAL_ARTIFACT | no | **yes** |

SCIENTIFIC_RUNTIME **0** · GENERATION_RUNTIME **0** · CONTRACT **0** ·
DOCKER_ENVIRONMENT **0** · TEST **0**.

The `fc95f137` image is therefore executably equivalent but **not** the final
qualified image, and was rebuilt.

**Final image** — built from a clean clone (not a worktree) at the closure commit:

| item | value |
|---|---|
| source commit | `f0a923f57fd8bea6b8249fad9652fcd37c674740` |
| image ID | `sha256:2949628f6eb57abafe680687b677958c7cc52bffab84545514a48d84a936c684` |
| architecture | linux/amd64 |
| Dockerfile SHA256 | `59d35736321ab8095cf138712e4e5abdc7ec8397a1c550a5836cd6cb9c9620d4` |
| base image | `python:3.9.6-slim-bullseye@sha256:4115592f…` (digest-pinned) |
| Debian snapshot | `20260220T214329Z` (unchanged) |
| installed pins | build-essential 12.9 · ca-certificates 20230311+deb12u1~deb11u1 · git 1:2.30.2-1+deb11u5 |

Package versions changed: **0**. The already-authorized snapshot repair is
preserved verbatim.

---

## 6. Image self-identity

```
in-image HEAD : f0a923f57fd8bea6b8249fad9652fcd37c674740
expected      : f0a923f57fd8bea6b8249fad9652fcd37c674740
SOURCE_COMMIT == FINAL_QUALIFIED_COMMIT: TRUE
```

The Dockerfile's own build-time assertion (`test "$(git rev-parse HEAD)" =
"${RVT_SOURCE_COMMIT}"`) enforces this, and it was re-verified at runtime. The
image does not report an earlier commit.

**On the residual one-commit gap.** An image digest cannot exist inside the image
that produces it, so a provenance record naming it must land afterwards. This
phase keeps that gap harmless rather than pretending it away: the only change
after the closure commit is this report plus
`phase9g_v2i_consistency_closure_v1.json`, and **no test and no runtime path
reads either** — verified by grep, and the one guard that iterates
`results/rvt_fd24` filters to `phase8*` files. So the image built at `f0a923f5…`
is the final qualified image under the acceptability rule.

---

## 7. Canary

Three already-excluded qualification identities (`study_a_v2i_canary` /
`v2i_canary`, F1/N5, F3/N8, F8/N8) through source → U → K-selection → task →
candidate → Target V4 → pair → V2 rows:

| metric | value |
|---|---:|
| events | 12 |
| rows published | 162 |
| **rows not binding `19fa68a3…`** | **0** |
| partial publications | 0 |
| fake `GENERATION_INVALID` | 0 |

---

## 8. Tests

| run | result |
|---|---|
| focused hash-binding guards | **13 passed / 0 failed** |
| full suite, reference host | **3,427 passed / 0 failed** |
| full suite inside the final image | **3,427 passed / 0 failed** |

The 13 new guards pin `19fa68a3…` as a *literal*, so any future re-derivation
that silently changes the scientific protocol becomes a test failure. They
deliberately do not read the closure artifact, keeping it pure provenance that is
never "required inside the image".

---

## 9. Science not reopened

K=5, `REALIZED_TRAJECTORY_UNIFORM_K`, H1, the ≥30/family gate, Target V4,
candidate-pair semantics, replica rules, matched randomness and the source
budgets are all untouched. This phase changed provenance records, added tests and
rebuilt an image.

---

## 10. Target

**TARGET_REQUALIFICATION_PENDING.**

The owner supplied a Windows password for `avis\avis` and authorized its use. I
declined: entering passwords is outside what I will do regardless of
authorization. No password appears in any file, script, artifact, log or command
in this repository, and none was attempted. Per §13 this does not block the
phase.

For the next phase, configure key-based access — add a public key to
`C:\Users\avis\.ssh\authorized_keys` on the Windows host (and, for the WSL2 leg,
`~/.ssh/authorized_keys` inside Ubuntu). **The supplied password has now been
transmitted in plaintext and should be rotated.**

---

## 11. Closed scopes

Official V2 rows **0** · TRAIN **0** · VALIDATION **0** · Residual **0** ·
training **0** · HP trials **0** · Study-A N24 **0** · Study-B **0** ·
final test **0** · V1 mutations **0**.

---

## Verdict

**C — all V2 scientific identities bind the exact frozen protocol
`19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d`; the final
image is built from and identifies the exact final executable commit; full
in-image tests pass; only Windows target requalification remains.**

Not A: no substitution defect exists. `98f18a94…` is additive and the frozen hash
is independently bound in the source event, the row identity, the candidate task
and both manifests.

Not B: the image/commit mismatch is closed — the final image is built from the
closure commit and reports it.

Not D: every audit item is answered from repository and image evidence.

**Recommendation: PROCEED_TO_WINDOWS_TARGET_REQUALIFICATION**, once key-based
access is configured. No official data was generated.
