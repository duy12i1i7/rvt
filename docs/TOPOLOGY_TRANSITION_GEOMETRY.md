# Topology Transition Geometry

## 1. Static contract

For the same persistent role in source topology `a` and target topology `b`:

```text
Delta_i(a,b) = r_i^b - r_i^a
```

`transition_geometry` reports role ID, source/target offsets, displacement,
magnitude, longitudinal and lateral components, the static swept line segment,
and the required lateral observation extent:

```text
|Delta_i,lateral|
+ robot_obstacle_required_clearance
+ transition_response_lateral_bound
+ protocol_lateral_drift_bound
+ transition_observation_margin.
```

All terms use the immutable runtime configuration. The function predicts no
dynamics and emits no safety state.

## 2. Symmetry

For every role and all six directed primary transitions:

```text
Delta_i(a,b) = -Delta_i(b,a)
```

The forward swept segment is the reverse segment with endpoints exchanged.
Magnitude and observation extent are direction symmetric under the current
zero extra drift/response assumptions.

## 3. Mechanical matrix

| N | Transition | Max displacement | Max lateral component | Observation extent |
|---:|---|---:|---:|---:|
| 5 | KEEP / COMPACT | 1.538 | 1.440 | 1.990 |
| 5 | KEEP / LINE | 1.610 | 1.080 | 1.630 |
| 5 | COMPACT / LINE | 1.138 | 0.540 | 1.090 |
| 6 | KEEP / COMPACT | 1.423 | 1.350 | 1.900 |
| 6 | KEEP / LINE | 2.012 | 0.900 | 1.450 |
| 6 | COMPACT / LINE | 1.423 | 0.450 | 1.000 |
| 8 | KEEP / COMPACT | 1.501 | 1.462 | 2.013 |
| 8 | KEEP / LINE | 2.490 | 1.012 | 1.562 |
| 8 | COMPACT / LINE | 1.855 | 0.450 | 1.000 |
| 12 | KEEP / COMPACT | 1.622 | 0.900 | 1.450 |
| 12 | KEEP / LINE | 4.269 | 1.350 | 1.900 |
| 12 | COMPACT / LINE | 2.737 | 0.450 | 1.000 |
| 16 | KEEP / COMPACT | 2.012 | 0.900 | 1.450 |
| 16 | KEEP / LINE | 5.566 | 1.350 | 1.900 |
| 16 | COMPACT / LINE | 3.628 | 0.450 | 1.000 |
| 24 | KEEP / COMPACT | 3.468 | 2.325 | 2.875 |
| 24 | KEEP / LINE | 8.796 | 1.875 | 2.425 |
| 24 | COMPACT / LINE | 5.419 | 0.450 | 1.000 |

Reverse transitions have identical magnitudes and opposite vectors. Every
required observation extent is within `R_obs=3.0 m`.

## 4. Explicit exclusions

This metadata is not a dynamic swept-envelope predictor, SAFE/UNSAFE/UNKNOWN
certificate, readiness vote, consensus phase, state machine, or protocol timing
rule. Those mechanisms are not implemented in Phase 3.
