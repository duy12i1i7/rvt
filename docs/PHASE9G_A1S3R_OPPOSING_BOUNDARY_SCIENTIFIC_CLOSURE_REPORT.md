# Phase 9G-A1S3R Opposing-Boundary Scientific Closure Report

## Verdict

**A. The owner pairing rule reveals another still-unfrozen scientific ambiguity.**

Stop code: **`S3_CENTERLINE_DEGENERACY_UNDERSPECIFIED`**.

The owner opposing-boundary rule is frozen additively for its nondegenerate domain,
but executable repair is not permitted yet. Authorized F6 S3 observations contain a
support exactly on the authoritative centerline, and no frozen epsilon or boundary-on-
centerline rule determines its side. No official generation was resumed.

## Identity

| Item | Value |
|---|---|
| Previous S3 evidence commit | `2d21f402ec286bde0f44494f612a2b83e2087184` |
| Previous S3 report commit | `5b0a439b739cdfd229aa1f124bdb4ed01bc65126` |
| A1S3R scientific-addendum audit commit | `7079a23` |
| Executable repair commit | None; mandatory scientific stop preceded implementation |
| Branch | `research/rvt-phase9g-a1s3r-opposing-boundary-v1` |
| Qualified scientific source | `8cf64481cd17b2c44f7007d3722a8110e53cae46` |
| Old image | `sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4` |
| New image | None; executable scientific code was not changed |
| STAGING checkpoint | `72cde9c6923f7eba0e6cbc9d18cb44d68fde7933a65907ad5501cf893df3001f` |

## Owner Rule

The additive artifact `rvt-s3-opposing-boundary-pairing/v1` freezes:

```text
d_k   = dot(p_k - c, n)
d_neg = max { d_k | d_k < 0 }
d_pos = min { d_k | d_k > 0 }
width = d_pos - d_neg
```

- `c`: existing compiled local corridor/reference center point at S3.
- `t`: existing oriented compiled corridor tangent; where no corridor exists, the
  existing compiled mission tangent.
- `n`: `(-t_y,t_x)`, the existing associated local normal.
- Pair: exactly one strictly negative-side and one strictly positive-side support.
- Same-side pairing, `abs(old_width)`, clamping, family logic, token order, outcomes,
  labels, and future trajectories are prohibited.

The diagnostic projection uses the already-authoritative free inner-surface support
coordinate: support-disc center shifted by its declared radius toward free space. It
does not tune against physical aperture.

### Degeneracy

The complete frozen authority contains no S3 rule for `d_k == 0`, no S3 geometric
epsilon, and no boundary-on-centerline validity rule. The audit found four authorized
robot observations where `circle-0`, the F6 central blocker, participates in the frozen
lookahead and has exactly:

```text
d_k = +0.0
float.hex() = 0x0.0p+0
```

These observations occur in three F6/N16 source instances:

- `train-f6-00`, episode 1, robot 14;
- `train-f6-01`, episode 1, robot 14;
- `validation-f6-00`, episode 0, robots 14 and 15.

Because `+0.0` satisfies neither `d_k < 0` nor `d_k > 0`, assigning, discarding, or
splitting the token would add science not supplied by the owner rule. No numerical
epsilon was introduced.

### Ties

Across 2,270 observations, 229 contain equal-distance representations, but all are
equivalent samples of the same physical component. No tie between physically distinct
components was found. Canonical, runtime, and reversed token orders produced zero
diagnostic semantic-projection mismatches.

## Mandatory Provenance

- Official generation had begun before the S3 defect was discovered.
- 342 official rows already existed.
- The dependency audit found 0 potentially affected and 0 proven affected rows.
- The blocked S3 transaction produced 0 committed scientific rows.
- The owner decision used only local physical geometry and anonymous support semantics.
- Target V4 outcomes, model performance, class balance, and downstream results were not
  used to select the rule.
- Historical scientific roots were not rewritten; the addendum is additive.

## Blocked F3 Case

Historical failure:

- source: F3/train-f3-01/N12/S3/episode 0, robot 8, source step 3;
- old pair: `corridor-0-left-4` and `corridor-0-left-3`;
- both tokens belong to physical component `corridor-0-left`;
- old width: `-0.6143634774571596 m`;
- independently reconstructed physical aperture: `1.361 m`.

The complete support table is in `phase9_s3_blocked_task_replay_v1.json`. Under the
owner local corridor frame at that exact failure call, all seven participating supports
are on the positive physical side. The nearest positive inner-surface coordinate is
`0.6632380738500273 m`; there is no observed negative-side support. Therefore the new
rule yields **no width at this call** and routes it to existing missing-side/UNKNOWN
behavior. It does not fabricate `abs(old_width)`.

No executable repaired source exists, so candidate replay and final downstream
scientific disposition were not run. Doing so after the F6 degeneracy stop would violate
the phase ordering.

## Population

All 250 authorized Study-A train/validation S3 source instances were reanalyzed. Study A
N24 and all sealed domains were excluded.

| Observation result | Count |
|---|---:|
| Robot observations | 2,270 |
| Valid negative-side support | 370 |
| Valid positive-side support | 370 |
| Both sides / width available | 318 |
| Missing one or both sides | 1,952 |
| Exact centerline degeneracy | 4 |
| Physically distinct tie | 0 |

For 318 nondegenerate opposing pairs, width statistics are:

- minimum: `0.6499999999999992 m`;
- median: `1.3999999999999997 m`;
- maximum: `1.4844000000000004 m`.

At the source-instance level, 71 instances contain at least one both-side observation,
90 contain a negative-side support, 86 contain a positive-side support, 245 have at
least one missing-side robot observation, and 3 contain centerline degeneracy. Five
source instances terminated under existing validity rules before this diagnostic.

The previous 20 negative instances and 48 negative robot observations are structurally
explained: every historical negative used two samples of one compiled boundary. The
generic owner projection prohibits that pair. There is no F3/F4 branch or family check.

## Token Invariance

For each of 2,270 observations, three token containers were evaluated: runtime order,
canonical scientific-identity order, and reversed order. Selected physical-component
equivalence and scalar projection had 0 mismatches.

Translation and rotation invariance follow from:

```text
dot((p+a)-(c+a), n) = dot(p-c, n)
dot(R(p-c), Rn)     = dot(p-c, n)
```

These are diagnostic owner-rule checks. No new executable path was created because the
centerline case prevents a total contract.

## Existing Official Data

The dependency cone was replayed independently on reference and qualified Docker:

| Classification | Rows |
|---|---:|
| `UNAFFECTED` | 254 |
| `DEPENDENCY_PRESENT_BUT_VALUE_VALID` | 88 |
| `POTENTIALLY_AFFECTED` | 0 |
| `PROVEN_AFFECTED` | 0 |

The 12 dependent source replays exercised 6,485 S3 calls:

- physical-pair differences: 0;
- S3 decision differences: 0;
- centerline-degenerate supports: 0;
- maximum width arithmetic difference: `6.661338147750939e-16 m`.

The tiny width differences come from equivalent frame-translation arithmetic. Width is
not serialized, every threshold decision is exact, and source semantic projection is
preserved by induction. Reference and Docker requalification digests match exactly.

**OFFICIAL DATA ACTION: `RETAIN_ALL_342`.** No row was rebuilt, rewritten, deleted, or
given a new ID.

## Replay And Regression

- Historical RB20 projection: unchanged because no runtime file changed.
- Existing 342-row source/recoverability projection: 0 unexplained mismatches.
- Blocked-task repaired replay: not run; no total executable rule exists.
- Representative repaired matrix: not run for the same mandatory stop reason.
- Complete test suite: `3107 passed`, 0 failed, one pre-existing PyTorch warning.
- Publication-required xfailed: 0.

## Performance And Timeout

The prior profile remains recorded as `W=12`, one numeric thread, chunk 1, timeout
243 s. No repaired production path exists, so performance qualification was not run and
the profile is classified `SUSPENDED_NOT_REQUALIFIED_FOR_S3R`. Timeout was not changed.

## Target And Image

Reference macOS/arm64 and the old qualified Docker image on target `100.71.102.9`
produced the same owner-rule semantic digest:

`34173283767f4b9cf09f3af5627bc0ab41f71ce81c1f36ae8b5be260c1950241`.

Both found the same four exact centerline observations. Existing-data semantic digests
also match. A new candidate production image was not built because executable repair
was scientifically prohibited; therefore exact-commit verification inside a new image
is not applicable.

Target isolation recheck passed:

- 210 candidate-pair transactions;
- 342 rows;
- checkpoint unchanged;
- STAGING mode `555`;
- zero partial files;
- zero phase containers;
- validation STAGING absent.

## Preflight

- Positive resume preflight: not eligible.
- Negative preflight: PASS; readiness is `BLOCKED_SCIENTIFIC_OWNER_DECISION`.
- Blocking code: `S3_CENTERLINE_DEGENERACY_UNDERSPECIFIED`.
- Escapes: 0.
- Scoped continuation authorization: not prepared or executed because science is not
  closed.

## Isolation

- Study A N24 accesses: **0**
- Study B accesses: **0**
- Final-test accesses: **0**
- Official generation resumed: **NO**
- Recoverability validation started: **NO**
- Residual V2 started: **NO**
- Training operations: **0**
- Official STAGING writes: **0**

## Canonical Artifacts

| Artifact | Canonical SHA-256 |
|---|---|
| Scientific addendum | `a5e7fa9ce92ba7fb449a76406da47cc00dd4a39ddee2e108a62a969589b5f6d3` |
| Population requalification | `f03ac6df5d9bcdf42914d20d8a08b74cd64f09d4e60e5fa9d3c060ddbcd55045` |
| Existing-data requalification | `4ae7d50f7dc09a6b96623b9b48af2da3e010d695c419c198d8991882f574e34e` |
| Resume readiness | `58b6aa14364f6aeb958bf1c7304a61ca958788f43c27fdda0316917bcd7a0ec4` |

## Final Verdict

**A. The owner pairing rule reveals another still-unfrozen scientific ambiguity.**
