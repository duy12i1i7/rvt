# Role-Dependent Opening Detector Validation

Source runtime: `cec0b408824883694ddaf3f7740688ecef2ab1cf`, tagged
`decentralized-parameter-semantics-v1`. This is a diagnostic comparison on the
preserved alpha 0.25 traces. Detector A is never used by the deployable runtime.

## Result

The old 1.2 m sector did miss wall material inside the outer robots' prospective
LINE-to-KEEP expansion band. Detector B covers every N=6 role-specific band, but
it does **not** delay the first swarm recovery evidence: the two centre roles use
a 0.55 m sector and become recovery originators earlier than detector A.

## Role Geometry

The derived half-width is

`abs(KEEP lateral - LINE lateral) + obstacle collision clearance + safety margin`.

Collision clearance is 0.55 m, safety margin is 0 m, and `R_obs` is 3.0 m.

| robot | LINE lat. (m) | KEEP lat. (m) | expansion (m) | clearance (m) | margin (m) | derived half-width (m) | max observable (m) | complete region observed |
|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| 0 | 0.00 | 0.90 | 0.90 | 0.55 | 0.00 | 1.45 | 3.00 | yes |
| 1 | 0.00 | 0.00 | 0.00 | 0.55 | 0.00 | 0.55 | 3.00 | yes |
| 2 | 0.00 | -0.90 | 0.90 | 0.55 | 0.00 | 1.45 | 3.00 | yes |
| 3 | 0.00 | 0.90 | 0.90 | 0.55 | 0.00 | 1.45 | 3.00 | yes |
| 4 | 0.00 | 0.00 | 0.00 | 0.55 | 0.00 | 0.55 | 3.00 | yes |
| 5 | 0.00 | -0.90 | 0.90 | 0.55 | 0.00 | 1.45 | 3.00 | yes |

## Frozen-Trace Comparison

Five previously failing alpha 0.25 traces were replayed with persistent-index
roles. The replay matches all 7,800 saved old-detector booleans (260 steps x 6
robots x 5 seeds): zero mismatches. The maximum along-coordinate difference from
the JSON traces is 0.00136 m, from stored numeric precision.

The table gives the range over seeds 0-4. A difference is `B - A`, so a negative
number means B declares the opening earlier.

| robot | A first evidence | B first evidence | difference (steps) | unique B-only wall points per trace | intersects future KEEP region |
|---:|---:|---:|---:|---:|:---:|
| 0 | 108-111 | 108-111 | 0 | 4 | yes |
| 1 | 91-94 | 30 | -64 to -61 | 0 | n/a |
| 2 | 113-117 | 113-117 | 0 | 4 | yes |
| 3 | 73-76 | 73-76 | 0 | 4 | yes |
| 4 | 43-44 | 30 | -14 to -13 | 0 | n/a |
| 5 | not observed | not observed | n/a | 2 | yes |

For robots 0, 2, 3, and 5, detector B admits obstacle returns in the interval
`1.2 m < abs(lateral) <= 1.45 m` that detector A excludes. Every reported B-only
point lies inside that robot's derived prospective KEEP expansion band. Other
wall points still blocked A at the eventual first-evidence step for robots 0, 2,
and 3, which is why their first-evidence timing is unchanged despite the proven
coverage defect.

For centre robots 1 and 4, B is intentionally narrower than A. Both see an open
0.55 m band at step 30. After the frozen 10-step commitment lock and 3-step
persistence rule, this permits recovery evidence at step 42.

## Deployment Check

- Detector A exists only inside the offline regression context manager.
- The context restores the runtime function after each diagnostic replay.
- The deployable runtime calls `forward_sector_half_width_for` and uses detector B.
- `guards.audit()` reports zero violations.

Raw evidence, including every B-only obstacle point, is in
`results/post_parameter_repair_regression/role_dependent_detector_validation.json`.
