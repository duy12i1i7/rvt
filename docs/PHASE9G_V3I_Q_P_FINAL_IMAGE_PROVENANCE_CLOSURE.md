# Phase 9G-V3I-Q-P — Final Image / Source Provenance Closure

**Verdict C. Recommendation `AUTHORIZE_OFFICIAL_RECOVERABILITY_V3_TRAIN_GENERATION` — TRAIN ONLY.**

| | |
|---|---|
| `FINAL_V3_EXECUTABLE_SOURCE_COMMIT` | `d635f17c8ef7e336fd54ff95a60dd608b61f3d7b` |
| `FINAL_V3_PRODUCTION_IMAGE_SHA256` | `sha256:a602ec015ff3d4063908f17e4d99087ce4aa89edda5853cf3483532eb53ab318` |
| canary semantic digest | `95dbdab76ce8066f6e535c09a86dca73bb4018e135c590a0ac72584b992df340` |
| full suite in final image | 4,317 passed / **0 failed** |
| official V3 rows | **0** |

---

## COMMIT CHAIN

| role | full SHA |
|---|---|
| implementation | `42d8012249a6773a9e047e4dc0098abdbb7ac3b6` |
| previously qualified image source | `beb65ba6eedcf0eebba07cde57a361b9956d15be` |
| **final closure** | `d635f17c8ef7e336fd54ff95a60dd608b61f3d7b` |

Branch HEAD at handoff was already the closure commit; the working tree was
clean. Branch `research/rvt-phase9g-v3i-q-p-final-image-provenance-v1` was cut
from it.

### Exact diff classification, `beb65ba6..d635f17c`

| classification | files |
|---|---:|
| `RUNTIME_SCIENCE_CODE` | **0** |
| `RUNTIME_NONSCIENCE_CODE` | **0** |
| `BUILD_INPUT` | **0** |
| `DEPENDENCY_INPUT` | **0** |
| `TEST` | 1 |
| `AUDIT_ARTIFACT` | 23 |
| `REPORT` | 1 |
| `OTHER` | 0 |

All 25 changes are **additions** (`A`); there are zero modifications, deletions
or renames. `rvt_swarm`, `scripts`, `docker`, `requirements.txt`,
`requirements.lock.txt`, `third_party`, `setup.py`, `pyproject.toml` and
`Makefile` are byte-identical across the range. A test re-derives this from git
rather than trusting the recorded table.

**So the previous image was scientifically complete and provenance-incomplete.**
No executable or build input changed after `beb65ba6`, which is why the phase's
preferred result holds and no defect is being hidden. What was wrong was
narrower and still worth fixing: the image's source commit was not the final
qualified closure commit, so an official dataset built with it would have had an
arguable relationship to the qualified source tree. That is the gap this phase
closes.

## FINAL IMAGE

Built once from a clean checkout of the exact closure commit, on the
Windows/WSL2 target — the authoritative production machine — because the
reference host is arm64 with no `linux/amd64` daemon, which the phase permits.

| | |
|---|---|
| source commit | `d635f17c8ef7e336fd54ff95a60dd608b61f3d7b` |
| image | `sha256:a602ec015ff3d4063908f17e4d99087ce4aa89edda5853cf3483532eb53ab318` |
| architecture | `amd64/linux`, 14 layers, 630,099,921 B |
| clean tree / untracked in context | 0 / 0 |
| tracked files | 1,719 |
| Dockerfile | `59d35736321ab8095cf138712e4e5abdc7ec8397a1c550a5836cd6cb9c9620d4` |
| lockfile | `4b8ae11c181ac1067abe29f5df188beaf54b81a088406029e495a6f4d1d0a1ac` |
| `.dockerignore` | `9a9a777a03b4f3f43ac986b68cd44ec6f08e93d27597b3f1c4226bb72bd9a394` |
| base image | `python:3.9.6-slim-bullseye@sha256:4115592f…` |
| Debian snapshot | `20260220T214329Z` |
| package upgrades | **0** |
| pins | Python 3.9.6 · torch 2.8.0+cpu · numpy 2.0.2 · pip 26.0.1 |

Source was materialized from three incremental git bundles applied in order,
each verified and each naming its prerequisite so a gap fails loudly:
`93085c2a…`, `48ea162b…`, `41cbeb0b…`.

### Two builds, both recorded

The **first** build from this same commit produced
`sha256:f1c55886…` at 1,054,019,016 B — 423 MB larger than its predecessor
despite an identical 244 MB working tree. Inspection found the cause: the clone
was made with a plain local `git clone`, which hardlinks the target repository's
entire 545 MB object store into the build context, and `.dockerignore` does not
exclude `.git` (the Dockerfile needs it for its `git rev-parse HEAD` check). The
image was scientifically correct, but roughly 405 MB of it was git objects
unreachable from this commit, making image content depend on clone mechanics
rather than on the source commit.

It was replaced by a `--no-local` clone that was garbage-collected before the
build, giving `.git` = 140 MB and the final 630,099,921 B image. Both attempts
are recorded; neither differs in source commit or in any executable file. Only
the second is authorized.

### Self-identity, read from inside the running image

```
SOURCE_COMMIT = d635f17c8ef7e336fd54ff95a60dd608b61f3d7b
probabilistic target  a127bf9fbe907c81f2cd8037e94164f738ee756d7480c7db6955d7405bc355b6
replica protocol      6c2143c4782f0d851205cb118a2ff1c3e33c8a6a3e3cdc2ce5a820106551fa9a
row binding V3        bdab65bdabbf503dc4d76d7d66d14c6504feb657b32d153a89643fab55058a8c
invalidity contract   66bdd9ffce3f0b6417f20c4b41602b5ea4be266a728bcdb1dd306b0e27ef5c75
layout registry V2    5494914e687a306b0288ce416e80d7c8a25f0f79377580eba58edc538d53680a
training loss         fc9c093327eaaa5ae95c038cf36a2a16ff2fee6d5fdc125dd1106bc3a99dfc11
Brier metric          0bf6dee325825953d856fb4f6b5df190879424b0d5e8d29cbe55ac930f682f04
source acquisition    19fa68a37d80f16ee1463b872f26402963daeb5a56f375423634a90dc1f3546d
Target V4             54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee
PYTHONPATH=/opt/rvt  PYTHONHASHSEED=0  OMP/MKL/OPENBLAS/NUMEXPR=1  MKL_CBWR=COMPATIBLE
RVT_FD24_NUMERICAL_EXECUTION_PROFILE_V1
```

Every hash was recomputed from its artifact at both nesting levels, not
string-matched. **No scientific hash changed.**

## SUITE

| run | passed | failed | seconds |
|---|---:|---:|---:|
| full suite in final image | **4,317** | **0** | 375.8 (wall 379.3) |
| focused invalidity + implementation | 171 | 0 | 0.3 |
| V1/V2 regression subset | 256 | 0 | 0.3 |

4,317 is exactly the expected closure count, so no count difference needs
explaining. The repository now collects 4,375 because this phase added 58
record-only tests **after** the image was built; a test asserts the delta is
exactly this file rather than merely "more than 4,317". No environment exemption
was used inside the image.

## NUMERICS

- **Brier, p = 0.5, k = 1, R = 3 → `0.25`** in the final image and on the reference host. The forbidden `(p − k/R)²` shortcut would give 0.0278.
- Grouped Bernoulli loss matches the written-out frozen formula on all six `(k, R)` patterns.
- **R = 1 is bit-identical to `binary_cross_entropy_with_logits`**: `0.5770118531164724` at k=0 and `1.0270118531164725` at k=1, equal by string comparison of the float64 `repr`.
- Event weights: `W(5,1) = W(16,1) = W(5,3) = W(16,3) = 0.525162949730635` — one distinct value.
- All 24 fixtures bit-identical to the reference host by float64 `repr`, not by tolerance.

## INVALIDITY

The owner-frozen matrix ran inside the final image: no R shrink · no Y
imputation · no replacement replica · no early scientific abort · all required
replicas execute · invalid pair → 0 supervised rows · audit evidence retained ·
infrastructure failure stays operational · S8 exact.

S8 in-image: numerator 0, denominator 94, rate 0.0, **PASS**. Censored
scientific-invalid rollouts stay in the denominator; unresolved infrastructure
failures stay out. Semantics changed by this phase: **0**.

## SEMANTIC CANARY

| where | digest |
|---|---|
| historical qualified (Phase 9G-V3I-Q-R) | `95dbdab7…92df340` |
| reference host, recomputed at closure commit | `95dbdab7…92df340` |
| final image on Windows target | `95dbdab7…92df340` |

**All three identical.** No new digest was blessed and no new official identity
was chosen — the run used the already-qualified non-official
`study_a_v3_qualification_canary` set, 4 episodes / 19 events / 270 rows,
F1·F8·F9, N ∈ {5, 6, 12}, R ∈ {1, 3}, overlap with official manifests 0.

W1 == W12 == reference, at 1 numeric thread per worker and chunk 1
(W1 208.9 s, W12 135.3 s). Replica-order permutation identical. Failure/resume:
0 duplicates, 0 partials, 0 seed substitutions, 0 identity changes, 0 early-abort
scientific path.

## TARGET

`ssh -o BatchMode=yes 'avis\avis'@100.71.102.9` — passwordless, no password
requested or used, no credential material recorded anywhere.

```
Windows      Microsoft Windows [Version 10.0.26200.9168]
WSL          2.7.10.0   kernel 6.18.33.2-2 (uname 6.18.33.2-microsoft-standard-WSL2)
WSLg         1.0.73.2
distribution Ubuntu-24.04, x86_64
CPUs         24 (Docker sees 24)
memory       33,323,393,024 B, 28 GiB available
Docker       29.6.1, API 1.55, linux/amd64
```

Full suite in the exact image: **4,317 / 0**. Semantic digest equals the
reference. The image was **not** rebuilt after qualification. Because it was
built on the target, the in-image run and the target run are one execution,
recorded once; the cross-platform comparison is against the canonical arm64
host.

## RUNTIME ANOMALY

The one-off segfault from Phase 9G-V3I-Q-R (a pre-existing decentralized-runtime
test, 1 occurrence followed by 7 clean runs) **did not reproduce** in this
closure across one complete 4,317/0 suite plus five further in-image executions —
the focused 171-test run, the 256-test V1/V2 regression, two canary passes and
one resume qualification. Cumulative non-reproducing runs: **13**.

Classification retained: **`TRANSIENT_NONREPRODUCED_RUNTIME_ANOMALY`**. Not
erased, not a science blocker, scientific protocol unchanged.

## V1 / V2

V1 unchanged, V2 unchanged, 256 historical regression tests pass inside the
final image. Historical gate 7 remains
**59 / 530 = 0.11132075471698114 > 0.10 — `FAILED_FOR_V2`**, untouched.

## OFFICIAL DATA

Official V3 TRAIN episodes executed **0** · VALIDATION episodes **0** ·
Target-V4 evaluations **0** · scientific rows **0** · qualification identities
overlapping official manifests **0** (episode 0, layout 0, geometry 0). Both dry
manifests still read executed 0 / generated 0 / rows 0, at 1,200 / 20 layouts /
60 per layout on offsets 0.22 + 0.54 and 300 / 10 / 30 on offset 0.65.

Sealed domains: N24 **0** · Study B **0** · final test **0** · training **0** ·
HP trials **0**. Executable code modified by this phase: **0**.

## FINAL PRODUCTION AUTHORITY

| | |
|---|---|
| source commit | `d635f17c8ef7e336fd54ff95a60dd608b61f3d7b` |
| image | `sha256:a602ec015ff3d4063908f17e4d99087ce4aa89edda5853cf3483532eb53ab318` |
| status | `FINAL_V3_PRODUCTION_IMAGE` |
| workers | 12 |
| numeric threads per worker | 1 |
| chunk | 1 |
| infrastructure timeout | 243.0 s |
| profile | `PROFILE_RECOVERABILITY_V1`, unchanged by this phase |

The predecessor `sha256:eaf52f74…` at source `beb65ba6…` is
**`PRE_FINAL_QUALIFICATION_IMAGE`**, **not authorized for official V3
generation**. Its history is retained, not deleted. There is no ambiguity
between the two.

---

## Artifacts

11 canonical-hashed records under `results/rvt_fd24/phase9g_v3i_q_p_*.json`,
plus 58 tests in `tests/test_phase9g_v3i_q_p_final_image_provenance.py`.

## Verdict

**C** — the exact final implementation closure commit is built into one
immutable `linux/amd64` production image; all final suites, canaries, numerics
and Windows-target checks pass; V1 and V2 remain unchanged; official V3 data
remain untouched; and this exact image is ready for official V3 TRAIN
generation. All 13 P21 criteria are met.

**Recommendation: `AUTHORIZE_OFFICIAL_RECOVERABILITY_V3_TRAIN_GENERATION` —
TRAIN ONLY.** VALIDATION generation, training and HP search remain unauthorized.
