# Phase 9G-A1S3 S3 Geometry / Width Scientific Specification Closure

## Verdict

**A. S3 remains scientifically under-specified and requires an explicit owner decision.**

Official generation remains blocked. No repair was implemented, no production image was
built, and no official data was modified.

## Identity

| Item | Value |
|---|---|
| A1R commit | `a943ca391fb5feb5c8e90a693f763cc47c4d4e2b` |
| A1S3 evidence commit | `2d21f402ec286bde0f44494f612a2b83e2087184` |
| Branch | `research/rvt-phase9g-a1s3-scientific-closure-v1` |
| Scientific source commit | `8cf64481cd17b2c44f7007d3722a8110e53cae46` |
| Old/qualified image | `sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4` |
| New image | None; source science was not changed |
| STAGING checkpoint | `72cde9c6923f7eba0e6cbc9d18cb44d68fde7933a65907ad5501cf893df3001f` |

The checkpoint preserves 210 train events, 420 candidate aggregates, 342 scientific
rows, zero duplicate scientific identities, and zero partial candidate-pair
publications. The parent and continuation run IDs remain unchanged.

## Blocked Task

- Study/split/family/layout: `study_a_zero_shot/train/F3/train-f3-01`
- Layout SHA-256: `59dd0a284ff8482c2831245429ba843d4439d9ec6f8735696ae84e651d714dd1`
- Team/source: `N=12`, `S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR`, episode 0
- Event: slot 0, control step 90, timestamp 13.5 s
- Current/candidate topology: COMPACT `5` / COMPACT `5`
- Failing local observation: robot 8, `role-0008`, source step 3, time 0.45 s
- Episode seeds: communication `1781318376`, data sampling `1073029205`, dynamic
  obstacle `976299567`, initial condition `808463837`
- Matched replica stream: replica 0, disturbance seed `1313388664`
- Atomic-unit ID: `7d7f2859e7f863031676d5c972dca4e03a4a5dd84ba438cdc7753bb26896b65b`

The canonical event and source identities are recorded in
`phase9_s3_width_derivation_v1.json`; they were not inferred from log text.

## Width Derivation

For each ego-relative support center `o`, mission tangent `t`, mission normal `n`,
support radius `r`, and lookahead `L`, the executable estimator computes:

```text
longitudinal = dot(o, t)
lateral     = dot(o, n)
admit iff 0 <= longitudinal <= L
inner       = abs(lateral) - r
left        = min(inner where lateral >= 0)
right       = min(inner where lateral < 0)
width       = left + right
```

Exact blocked operands:

| Quantity | Value (m) | `float.hex()` |
|---|---:|---|
| Lookahead | 2.5650000000000004 | `0x1.4851eb851eb86p+1` |
| Left lateral projection | 0.06365147099135524 | `0x1.04b767a400ab6p-4` |
| Left inner projection | -0.2863485290086447 | `-0x1.25388c7d663b8p-2` |
| Right lateral projection | -0.021985051551485182 | `-0x1.6833fd5a87374p-6` |
| Right inner projection | -0.3280149484485148 | `-0x1.4fe32690bdf2fp-2` |
| Measured width | **-0.6143634774571596** | `-0x1.3a8dd98712174p-1` |

The selected tokens were `corridor-0-left-4` and `corridor-0-left-3`. They lie on
opposite signs of the ego mission normal, but both are samples of the same compiled
physical `left` boundary component. Their binary64 width is `bfe3a8dd98712174`.

Reference macOS/arm64 and the qualified Linux/x86_64 production image reproduced the
exact same operands, support identities, exception, binary64 value, and population
semantic digest. This is not a numerical-portability defect.

Reversing token order and the representational lateral axis only swaps selector labels;
the value remains bit-identical. A rigid 90-degree rotation of tokens and mission axes
also remains bit-identical. The defect is therefore not an orientation sign reversal.

## Physical Geometry

Independent reconstruction from the source layout, rather than the failed statistic,
gives:

- analytic polyline corridor centerline: `(-2.5,-0.755) -> (0,0.755) ->
  (2.5,0.5208583333333333)` m;
- half width: `0.6805` m;
- physical free width: `1.361` m;
- entry aperture: `1.3610000000000002` m;
- exit aperture: `1.361` m;
- dynamic obstacles: none.

Classification: **A, physically positive-width / feasible**. The negative scalar is
caused by pairing overlapping support discs from one curved boundary component, not by
negative physical passage clearance or invalid source geometry.

## Authority And S3 Meaning

Current frozen authority defines S3 as the deployable robot-local geometric selector.
It consumes own state, fresh one-hop messages, ego-relative obstacle support discs,
mission direction, local COMPACT/LINE role metadata, and local lifecycle state. Its
requests feed Phase-7 transition origination and therefore can indirectly affect source
state/event timing, candidate rollouts, Target V4, ego graphs, identities, and labels.
Target V4 does not consume width directly.

The frozen width statistic is the **unsigned minimum free inner-surface separation from
paired left/right boundary supports in the role-dependent lookahead sector**. A negative
width is not mathematically permitted; the pure decision contract rejects it. The frozen
prose says contradictory or incomplete data is `UNKNOWN`, but does not specify how to
recover opposite physical boundary components from anonymous `(dx,dy,radius)` tokens
when one curved component crosses both signs of the mission normal.

No current, superseded, historical, or diagnostic source supplies that missing pairing
rule. Historical and diagnostic evidence was not promoted to scientific authority.

## Classification

**CASE IV: the current frozen specification does not determine what to do.**

- Case I does not apply: although width is unsigned, the result is not a signed,
  orientation-dependent implementation value.
- Case II does not apply: the frozen quantity is not signed.
- Case III does not apply: the independently reconstructed geometry is valid and has
  positive free width.

The exact missing definition and three coherent alternatives are frozen in
`phase9_s3_owner_decision_required_v1.json`:

1. Treat a contradictory/nonnegative-impossible pair as `HOLD_UNKNOWN`.
2. Define deterministic robot-local support-component reconstruction.
3. Add opaque deterministic boundary-component identity to local support tokens.

Option 1 is recommended because it reuses the frozen UNKNOWN behavior and changes the
smallest scientific surface. It is still a new scientific rule and was **not**
implemented.

## Population Audit

The audit enumerated all 250 authorized Study-A train/validation S3 source instances,
excluding N24 and all sealed domains. Diagnostic state was fixed after three unmodified
source steps and before the first post-persistence selector call.

| Level | Count | Positive | Zero | Negative | Unknown/no pair | Source terminated |
|---|---:|---:|---:|---:|---:|---:|
| Source instances | 250 | 56 | 0 | 20 | 169 | 5 |
| Robot observations | 2270 | 293 | 0 | 48 | 1929 | n/a |

Non-null robot widths have minimum `-0.6237564939010709` m, median
`1.3999999999999992` m, and maximum `1.4844000000000008` m.

By affected family/team size:

| Family | N | Negative source instances | Negative robot observations |
|---|---:|---:|---:|
| F3 | 8 | 2 | 2 |
| F3 | 12 | 5 | 10 |
| F3 | 16 | 5 | 23 |
| F4 | 8 | 3 | 3 |
| F4 | 12 | 5 | 10 |

All 48 negative observations use same-component pairs, all corresponding compiled
passages have positive width, and every value is invariant to the diagnostic
left/right/order reversal. The condition is systematic in curved F3/F4 geometry, not a
single episode.

## Existing Official Data

All 342 rows were traced through their source transaction dependency cone:

| Classification | Rows |
|---|---:|
| `UNAFFECTED` | 254 |
| `DEPENDENCY_PRESENT_BUT_VALUE_VALID` | 88 |
| `POTENTIALLY_AFFECTED` | 0 |
| `PROVEN_AFFECTED` | 0 |

The 60 dependent transactions span 12 exact source replays. Every source snapshot or
termination matches committed evidence, and no negative width occurs in the committed
dependency cone. No row was deleted, rewritten, regenerated, compacted, or deduplicated.

**DATA ACTION: `OWNER_DECISION_REQUIRED`.** All 342 rows remain preserved official
evidence and currently have zero proven impact. A final continuation/data policy cannot
be declared until the owner freezes future ambiguous-pair semantics. No transaction
rebuild is justified now.

## Coverage And Tests

The earlier mechanical tests used hand-selected nonnegative widths. RB20 covered
F1/S1, F9/S0, F8/S1, and F5/S1. The 9G0-R canary and 9G0-P benchmark covered
F1/F2/F5/F8/F9/F10, not curved F3/F4 S3 runtime geometry. Previous preflight checked
structure and pure contracts but did not enumerate runtime support pairing over the
authorized curved-layout population.

New fail-fast coverage checks the exact F3/N12 source before event step 90, positive
straight controls, binary64/orientation invariance, F3/F4 across multiple N, the source
validity path, canonical data impact, and blocked readiness.

- Focused geometry/generation/candidate-pair/Target-V4/RB20/9G0-R/9G0-P/A1R suite:
  `406 passed`.
- Complete suite: `3095 passed`, 0 failed, one pre-existing PyTorch warning.
- Publication-required xfails: 0.

## Repair And Operations

No executable conformance repair can be derived from frozen authority. Any proposed
pairing behavior is new science. Consequently:

- runtime/controller/safety/geometry/event/Target-V4 code changes: 0;
- scientific semantic changes: 0;
- production image builds: 0;
- performance requalification: not applicable;
- qualified `W=12`, threads `1`, chunk `1`, timeout `243 s`: retained but unusable until
  separate continuation authorization after scientific closure.

Generation readiness is `BLOCKED_SCIENTIFIC_OWNER_DECISION`.

## Isolation

- Official generation resumed: **NO**
- Recoverability validation started: **NO**
- Residual V2 started: **NO**
- Training operations: **0**
- Study A N24 accesses: **0**
- Study B accesses: **0**
- Final-test accesses: **0**
- Official STAGING writes during A1S3: **0**

## Canonical Evidence

| Artifact | Canonical SHA-256 |
|---|---|
| Width closure | `2fafc2a24402c61afecf68df701df3cac474652b519599ecee96575dcc5133ee` |
| Geometry authority | `6f31a44b4ac514d0019f9b55d01ff8827e16f6423c978da283215322fc18f20f` |
| Population closure | `82bb879ee193430130ed4cd24313f491c826bdc3629873c506fb24628782f3f2` |
| STAGING dependency audit | `10a5db0e85894646ec21c040b676546714ceb139bc7e1ab05eb40f99a74024d3` |
| Official-data impact | `681f6f3585a7ed3e17bafd9049d0e611af4735da33a95a9dd76334535d58c8bb` |
| Owner decision | `f0613c95981ed6f948c4a894e0c42e38cec0bdf372e588b5c1986617682479b6` |
| Scientific closure | `bd757731f150df704085eef3ac6ceb49a5740300415faaeaaf510cf06938496b` |
| Generation readiness | `28a50928afbbf3ce1f07d1d83aeb1d8b8c753638f693ef5261ee8b8b68019306` |

## Final Verdict

**A. S3 remains scientifically under-specified and requires an explicit owner decision.**
