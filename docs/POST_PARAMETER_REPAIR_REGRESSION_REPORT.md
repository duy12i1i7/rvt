# Post-Parameter-Repair Regression Report

Branch `research/post-parameter-repair-regression-v1`; frozen runtime commit
`cec0b408824883694ddaf3f7740688ecef2ab1cf`; tag
`decentralized-parameter-semantics-v1`. No learned selector, final-test layout,
controller change, corridor change, parameter tuning, or new protocol phase was
used. Closed-loop experimental claims remain N=6 only.

## Verdict

> **B. The detector is now correct, but a distributed safe-expansion certificate is still necessary.**

This is decision CASE 2. The parameter repair fixes the detector's role geometry,
but a centre robot's valid local opening evidence is propagated into a common
KEEP commitment while outer robots remain locally unsafe to expand.

## Frozen Evaluation

Each arm uses the complete 30-episode set: alpha 0.25/0.35/0.45, two published
geometry variants, and seeds 0-4. The pre-repair V3 arm is the preserved published
artifact, not a reconstructed rerun.

| arm | crossing | collision-free | KEEP dwell | full success | median epochs | no-op | mean bytes |
|---|---:|---:|---:|---:|---:|---:|---:|
| always KEEP | 0.067 | 1.000 | 0.000 | 0.000 | 0 | 0 | 375,781 |
| always LINE | 1.000 | 1.000 | 0.000 | 0.000 | 0 | 0 | 232,113 |
| preserved pre-repair V3 | 0.667 | 1.000 | 0.500 | 0.500 | 2 | 0 | 305,333 |
| **corrected parameterized V3** | **0.467** | **1.000** | **0.467** | **0.467** | **2** | **0** | **331,656** |

### Corrected Runtime by Alpha

| cell | crossing | collision-free | KEEP dwell | full success | median epochs | no-op |
|---|---:|---:|---:|---:|---:|---:|
| **alpha 0.25** | **0.00** | 1.00 | **0.00** | **0.00** | 2 | 0 |
| alpha 0.35 | 0.40 | 1.00 | 0.40 | 0.40 | 2 | 0 |
| alpha 0.45 | 1.00 | 1.00 | 1.00 | 1.00 | 2 | 0 |

Relative to preserved V3, alpha 0.25 stays at 0.00; alpha 0.35 regresses from
1.00 crossing / 0.70 full to 0.40 / 0.40; alpha 0.45 improves from 1.00 crossing
/ 0.80 full to 1.00 / 1.00. Pooling therefore does not hide alpha 0.25.

## Closed-Loop Mechanism

All corrected episodes perform KEEP -> LINE at step 30 and LINE -> KEEP at step
42. Centre roles use the derived 0.55 m sector and have raw forward-opening
evidence from step 30. After the commitment lock releases, their persistent
evidence originates recovery at step 42. Outer roles use 1.45 m sectors and are
still blocked by wall returns at the same commit time in every failed episode.

The protocol itself is consistent: zero confirmation disagreements, zero unsafe
partial commitments, exactly two successful epochs per episode, zero retries,
and zero no-op epochs. The failure is the semantics of allowing one locally safe
role to authorize simultaneous physical expansion for locally unsafe roles.

## Predeclared Gates

| gate | result | measurement |
|---|:---:|---|
| P1 detector geometry | **PASS** | all six role sectors cover the prospective band; no deployable 1.2 m literal |
| P2 decentralization | **PASS** | zero strict-runtime guard violations; no exit plane, centroid, or centralized trigger |
| P3 propagation | **PASS** | path trigger/confirmation covers declared diameter; no partial closed-loop commit |
| P4 closed-loop passage | **FAIL** | crossing 0.467 < 0.80; collision-free 1.00 >= 0.95 |
| P5 full reconfiguration | **FAIL** | KEEP dwell/full 0.467 < 0.70 |
| P6 epoch control | **PASS** | no-op 0; median epochs 2; successful episodes have one transition each way |
| P7 alpha 0.25 | **REPORTED** | crossing/dwell/full all 0.00 |

## Mechanical Parameterization

| N | `delta_N` | max sector (m) | `R_obs` (m) | diameter rounds | construction/propagation |
|---:|---:|---:|---:|---:|:---:|
| 5 | 1.610 | 1.630 | 3.0 | 4 | pass |
| 6 | 2.012 | 1.450 | 3.0 | 5 | pass |
| 8 | 2.490 | 1.562 | 3.0 | 7 | pass |

Role construction contains no fixed-size branch, every role receives a width,
outer roles are wider where required, and widths increase with formation spacing
and collision clearance. Trigger and confirmation pass the worst-case path
contract. These are mechanical checks only for N=5 and N=8; no closed-loop claim
is made beyond N=6. KEEP/LINE tube disjointness holds in all three checks and is
currently supported for N >= 5.

## Required Answers

1. **Did 1.2 m miss outer expansion-path wall material?** Yes. Each alpha 0.25
   trace contains 2-4 unique B-only wall points per outer role, all intersecting
   its future KEEP band.
2. **Does the role-dependent sector delay alpha 0.25 recovery evidence?** No.
   Outer timing is unchanged on the frozen trace, while centre evidence moves
   earlier; corrected closed loop commits recovery at step 42.
3. **Does it avoid premature lateral expansion?** No. Outer roles remain locally
   wall-constrained at common KEEP commitment in every failed episode.
4. **Does alpha 0.25 cross?** No, 0/10.
5. **Does alpha 0.25 complete KEEP dwell?** No, 0/10.
6. **Do alpha 0.35/0.45 retain performance?** Alpha 0.35 regresses to 0.40 full;
   alpha 0.45 improves to 1.00 full.
7. **Median epochs at most three?** Yes, 2.
8. **Are trigger and confirmation correct?** Yes, for the declared diameter
   contract and all frozen closed-loop episodes.
9. **Is a separate distributed safe-expansion certificate necessary?** Yes. The
   remaining failure is cross-role safety at common commit, not detector geometry.
10. **What remains N=6-specific?** Every closed-loop rate, timing, trajectory,
    corridor result, and failure count. N=5/8 have mechanical tests only.

## Stop Condition

No safe-expansion consensus, additional protocol phase, learned selector, or
post-result parameter change has been implemented. Work stops at this report.

Machine-readable artifacts are under
`results/post_parameter_repair_regression/`.
