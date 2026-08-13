# Phase 9G-A1S3Z Exact-Centerline Scientific Closure Report

## Verdict

**C. Exact-centerline S3 semantics are closed, all existing 342 rows remain
valid, the executable implementation is qualified, and Study-A Recoverability
may be separately authorized to resume.**

This phase did not authorize or perform that resume.

## Identity

| Item | Value |
|---|---|
| A1R evidence commit | `a943ca391fb5feb5c8e90a693f763cc47c4d4e2b` |
| A1S3 evidence commit | `2d21f402ec286bde0f44494f612a2b83e2087184` |
| A1S3 report commit | `5b0a439b739cdfd229aa1f124bdb4ed01bc65126` |
| A1S3R evidence commit | `7079a23bab9a5eed4c4e864988c0139d937009d4` |
| A1S3R report commit | `eb71541eb8d611c350aa856f9da28165757f3e6c` |
| Exact-centerline addendum commit | `295722307412a85cba5506fb2abc62dcf23a99f3` |
| Initial repair commit | `74de65a81f3aa897be326e57de29297f5cc237e4` |
| Qualified runtime repair commit | `20bfa1bfdc311f67075327418595441b101bc8de` |
| Final image source commit | `848e8b352a91e95af777ebbeccd5fbb43d53777e` |
| Branch | `research/rvt-phase9g-a1s3z-exact-centerline-v1` |
| Old image | `sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4` |
| New image | `sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90` |
| STAGING checkpoint | `72cde9c6923f7eba0e6cbc9d18cb44d68fde7933a65907ad5501cf893df3001f` |

The rejected intermediate image
`sha256:88f4d7d833ec7166d3b946b31cae5fa8b6499e06e38370b9cb9f83bfacd29810`
is retained as evidence: S4 delegated S3 evidence but did not receive the local
frame. Image
`sha256:c2f8734403f6422c10e04531529458e7826c175cbec0933c5b7d936cebedf39f`
contains the qualified runtime repair and was used for the scoped performance
benchmark. The final image adds exact source/artifact/test binding without
changing that runtime path.

## Owner Rule

The additive `rvt-s3-exact-centerline-support/v1` rule is:

```text
if d_k == 0.0: CENTERLINE_NEUTRAL
elif d_k < 0.0: NEGATIVE
else: POSITIVE
```

Both IEEE-754 `+0.0` and `-0.0` are `CENTERLINE_NEUTRAL`. No sign-bit
assignment is used. No epsilon, `isclose`, rounding, clamping, snapping,
perturbation, or other fuzzy classification is present.

Neutral support is excluded only from the S3 opposing-boundary extrema. It is
not removed from the physical scene. `circle-0` remains a radius-0.8 m circle
obstacle in collision geometry, safety geometry, controller observations,
simulator execution, clearance calculations, and Target V4.

After neutral classification, the prior owner rule remains unchanged:

```text
d_neg = max { d_k | d_k < 0 }
d_pos = min { d_k | d_k > 0 }
width = d_pos - d_neg
```

Missing-side observations use the existing `HOLD_UNKNOWN` behavior. No new
validity rule or synthetic boundary was added. Nonfinite input still uses the
existing fail-closed guard.

## Four F6/N16 Cases

All four observations use scientific/physical support `circle-0`, a circle
obstacle centered at world position `[0.0, 0.0]` with radius `0.8 m`.

| Split/layout | Episode | Step | Robot | `d_k` / hex | NEG | POS | Neutral | Pair / width | Existing downstream disposition |
|---|---:|---:|---:|---|---|---|---|---|---|
| train/train-f6-00 | 1 | 3 | 14 | `+0.0` / `0x0.0p+0` | empty | empty | `circle-0` | none / `null` | `HOLD_UNKNOWN` |
| train/train-f6-01 | 1 | 3 | 14 | `+0.0` / `0x0.0p+0` | empty | empty | `circle-0` | none / `null` | `HOLD_UNKNOWN` |
| validation/validation-f6-00 | 0 | 3 | 14 | `+0.0` / `0x0.0p+0` | empty | empty | `circle-0` | none / `null` | `HOLD_UNKNOWN` |
| validation/validation-f6-00 | 0 | 3 | 15 | `+0.0` / `0x0.0p+0` | empty | empty | `circle-0` | none / `null` | `HOLD_UNKNOWN` |

The full support table contains only `circle-0` in the S3 lookahead for each
of these robot observations, so an opposing pair does not remain after neutral
classification. This is resolved by the already-frozen incomplete-observation
rule; it is not an unresolved missing-side ambiguity.

The authoritative frame values are:

| Layout / robot | `c` world meters | `n` |
|---|---|---|
| train-f6-00 / 14 | `[-2.807894820286387, -0.09112086674299373]` | `[-0.03243459255297831, 0.9994738601914122]` |
| train-f6-01 / 14 | `[-2.8142005384302653, -0.09047185697630232]` | `[-0.032131733301750905, 0.999483642545002]` |
| validation-f6-00 / 14 | `[-2.790803710378242, -0.09182674475047876]` | `[-0.03288553672527958, 0.9994591244639726]` |
| validation-f6-00 / 15 | `[-2.8340650178563527, -0.09325018597086686]` | `[-0.03288553672527958, 0.9994591244639726]` |

Each of the three source traces was replayed twice. Repeated semantic digests
were exact, the next source step completed without termination, and the
physical-scene inventory digest was unchanged before/after. No official row was
committed.

## Population

All 250 authorized nonsealed Study-A train/validation S3 source instances were
audited. They comprise 245 active instances and 5 instances handled by existing
source-invalid rules. At source-instance level, 90 contain a negative-side
observation, 86 contain a positive-side observation, 71 contain a both-side
observation, 245 contain at least one missing-side observation, and 3 contain
one or more of the four exact-neutral observations.

The 245 active instances yielded 2,270 robot observations:

| Robot-observation/support result | Count |
|---|---:|
| Participating support observations | 5,000 |
| NEG support observations | 2,465 |
| POS support observations | 2,531 |
| CENTERLINE_NEUTRAL support observations | 4 |
| Both opposing sides / valid width | 318 |
| Missing NEG | 1,900 |
| Missing POS | 1,900 |
| Equal-coordinate representation tie | 229 |
| Physically distinct tie | 0 |

The 229 representation ties are multiple samples of the same physical
component; no physical identity ambiguity exists. Runtime, canonical, and
reversed token order were compared for every observation, for 6,810 total
order projections, with 0 semantic mismatches.

For the 318 valid pairs, width was:

- minimum `0.6499999999999992 m`;
- median `1.3999999999999997 m`;
- maximum `1.4844000000000004 m`.

The previous F3/F4 population remains correct: 20 historical negative source
instances and 48 negative robot observations, no same-side pair, and no
centerline-induced regression. The original blocked F3 task still has no NEG
support, nearest POS `0.6632380738500273 m`, width `null`, and existing
`HOLD_UNKNOWN` behavior.

Signed-zero, smallest finite positive/negative values, token order, translation,
and rotation were tested explicitly. `-0.0` and `+0.0` have identical semantics;
every finite nonzero value retains its strict sign.

## Existing Data

The combined opposing-boundary plus exact-centerline dependency cone was
replayed independently on reference macOS/arm64 and the final qualified
Docker/Linux x86-64 image. Semantic projection digests match exactly.

| Classification | Rows |
|---|---:|
| `UNAFFECTED` | 254 |
| `DEPENDENCY_PRESENT_BUT_VALUE_VALID` | 88 |
| `POTENTIALLY_AFFECTED` | 0 |
| `PROVEN_AFFECTED` | 0 |

The 88 dependent rows cover 60 transactions and 6,485 S3 calls. There are 0
decision differences, 0 selected-physical-pair differences, and 0 changed
scientific row projections. No row, ID, label, or historical provenance payload
was rebuilt or rewritten.

**OFFICIAL DATA ACTION: `RETAIN_ALL_342`.**

The target recheck found the same 210 completed train transactions/events, 420
candidate aggregates, 342 rows, 0 duplicate scientific identities, and 0
partial candidate-pair publications. The canonical checkpoint hash is unchanged.

## Regression

- F3/F4: 20 source instances and 48 robot observations retained the repaired
  owner-rule result; 0 regression.
- RB20: 4 source episodes, 14 Recoverability rollouts, and 36 diagnostic residual
  candidate evaluations; 0 identity or semantic mismatches and 0 rows.
- Official producer canary: 12 Recoverability candidate aggregates; 0 failures,
  timeouts, semantic mismatches, or official writes.
- Matched randomness: 21,000 groups; 0 candidate-pair seed mismatches; all 3,000
  F8/F9 events had three distinct matched seeds where required.
- Candidate-pair transaction, Target V4, isolation, and 9G0-R binding tests: 0
  unexplained mismatch.

The 36 residual evaluations are RB20 conformance diagnostics only. Official
Residual V2 was not started and no residual row was generated.

## Performance

The real Recoverability producer ran a predeclared diagnostic set containing
normal S3, old F3/F4 negatives, F6/N16 exact-centerline cases, and a non-S3
control.

| Field | Result |
|---|---:|
| Workers | 12 |
| Numeric threads per worker | 1 |
| Chunk | 1 atomic unit |
| Infrastructure timeout | 243 s |
| Candidate aggregates | 12 |
| Median aggregate wall time | `0.9648314704973018 s` |
| p90 | `2.6462980871932817 s` |
| p95 | `2.8705217862472634 s` |
| Maximum | `2.9642586190020666 s` |
| Maximum timeout utilization | `0.0121985951399262` |
| Timeouts / failures / writes | `0 / 0 / 0` |

Classification: **`RECOVERABILITY_PROFILE_REMAINS_QUALIFIED`**. The profile was
not changed.

## Target

Target `100.71.102.9` passed exact image/commit verification:

- image digest exactly
  `sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90`;
- OCI revision and in-image clean Git HEAD exactly
  `848e8b352a91e95af777ebbeccd5fbb43d53777e`;
- original target checkout remained clean at
  `6bcfc0e26c4b327ba63f2844eaa02d30d56903ba`;
- reference and Docker population semantic digest exactly
  `c204c15dee97a3f400b0cb05c8676bac9d065ead121d7cb97071fa3b4615c163`;
- reference and Docker existing-data semantic digest exactly
  `709a9dd0af12a8d27a5b188233d3f2a2bf3acaedd07956a283a427f461b9f828`;
- STAGING remained read-only, directory mode `0555`, with no partial transaction;
- checkpoint remained
  `72cde9c6923f7eba0e6cbc9d18cb44d68fde7933a65907ad5501cf893df3001f`.

The first full-suite attempt directly in immutable `/opt/rvt` had 27 test-setup
permission failures because those tests create temporary injected modules below
the source tree. It was not accepted as a scientific suite. Re-running the exact
image tree in a writable, unmodified temporary copy passed completely.

## Preflight

The exhaustive robot-observation guard reports:

| Category | Count |
|---|---:|
| Normal opposing pair | 318 |
| Centerline neutral present and pair still resolvable | 0 |
| Existing incomplete observation -> `HOLD_UNKNOWN` | 1,952 |
| Existing source-invalid instance | 5 source instances |
| Missing-side unresolved | 0 |
| Tie unresolved | 0 |
| Escapes | 0 |

`missing-side unresolved` and `tie unresolved` are executable fail-closed paths.
Positive preflight passed while explicitly preserving
`official_resume_authorized_now=false`. Failure injection for each negative path
stopped with its declared code.

The future authorization artifact is only a proposal. Its possible scope is
Study-A Recoverability TRAIN continuation; it has no owner signature and grants
no execution authority. Validation remains gated on TRAIN completion and
reconciliation.

## Tests

- Local complete suite: `3127 passed`, 0 failed, 1 warning, 385.89 s.
- Target exact-image complete suite: `3118 passed`, 0 failed, 1 warning,
  378.90 s.
- Target exact-image focused suite: `125 passed`, 0 failed, 1 cache warning,
  61.05 s.
- Final closure/runtime focused suite: `85 passed`, 0 failed.
- Publication-required xfailed: 0.

## Isolation

- Study A N24 accesses: **0**
- Study B accesses: **0**
- Final-test accesses: **0**
- Official generation resumed: **NO**
- Recoverability validation started: **NO**
- Official Residual V2 started: **NO**
- Training operations: **0**
- Official STAGING writes: **0**

## Canonical Artifacts

| Artifact | Canonical SHA-256 |
|---|---|
| Exact-centerline scientific addendum | `d216217b3a3dfead5e3249cbf57317a71aa1c479acc840994eec9ff1616da23b` |
| Centerline execution contract | `8b52c88efbcf8d750d964f57573edf9e82a9757aebc082ef6bf15e931dba1041` |
| Population requalification | `cf496a27e36d9c929d038422e312b7d55d88df62d55237dbd992c9e4264f4103` |
| Existing-data requalification | `75a4ae8875eddae03bea06b09a9567cca926b03a1e161fd7a37c6c962ed1debb` |
| Centerline replay | `fdc3fc58b6c1e6a11b9e1816d945001244a8a466ef6f6ff853897ba609c1e06c` |
| Target validation | `f9ea7d7a4d46a60584df2a4af9b2dd2bae7aac608163d33d1443f71ff61172c6` |
| Current generation provenance v3 | `9f209cd4b5ae591b2f576a085bcbdb6b7d30a7f3fecb9840d6e0eb56bb03adc8` |
| Final S3 resume readiness | `a7118241538639b4da657f5aceff89bdfe9c64be62f22a21221b221016637d6c` |
| Current generation readiness v5 | `3a0890c84da624229d2efde6be335bb8868a1805a95e9584e077c39463464d3c` |

## Final Verdict

**C. Exact-centerline S3 semantics are closed, all existing 342 rows remain
valid, the executable implementation is qualified, and Study-A Recoverability
may be separately authorized to resume.**

Official generation remains stopped pending a separate owner authorization.
