# Phase 6 Formation Stabilization Report

The frozen stabilization matrix contains 360 episodes: six team sizes, three
forced topologies, four fixture classes and five predeclared seeds. All 360
initial conditions were accepted on the first deterministic construction; no
episode was rejected, replaced or resampled.

Every one of the 72 `(N, topology, fixture)` cells passed the frozen gates:
collision-free rate and final Metric V3 dwell completion were both 1.00, with
no deadlock, nonfinite state, solver failure or infeasible projection. The
minimum robot-robot distance over the complete matrix was 0.7394 m. The largest
final formation error was 0.0034 m, below the unchanged Metric V3 tube. Every
fixture started inside that tube by construction, so first tube entry was at
0.00 s and the unchanged 3 s dwell completed at 2.85 s under the discrete
sampling convention.

`CF`, `Dwell` and `Dead` are rates. `Efinal` is the largest final error among
the five seeds, `dmin` is the minimum center distance, and `lat` is the median
of episode-level median per-robot controller latency. Saturation and projection
rates were zero in stabilization. Exact per-episode values, including initial
and maximum error, p95/p99 latency and controller calls, are preserved in
`results/phase6_forced_topology/stabilization/episodes.{json,csv}`.

| N | Topology | Fixture | n | CF | Dwell | Dead | Efinal (m) | dmin (m) | tube (s) | complete (s) | lat (ms) |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | KEEP | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0008 | 0.8335 | 0.00 | 2.85 | 0.451 |
| 5 | KEEP | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0015 | 0.8143 | 0.00 | 2.85 | 0.444 |
| 5 | KEEP | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0017 | 0.8273 | 0.00 | 2.85 | 0.442 |
| 5 | KEEP | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.447 |
| 5 | COMPACT | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0008 | 0.8279 | 0.00 | 2.85 | 0.442 |
| 5 | COMPACT | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0018 | 0.7953 | 0.00 | 2.85 | 0.444 |
| 5 | COMPACT | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0019 | 0.7632 | 0.00 | 2.85 | 0.441 |
| 5 | COMPACT | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.442 |
| 5 | LINE | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0007 | 0.8375 | 0.00 | 2.85 | 0.439 |
| 5 | LINE | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0020 | 0.8146 | 0.00 | 2.85 | 0.439 |
| 5 | LINE | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0019 | 0.8058 | 0.00 | 2.85 | 0.439 |
| 5 | LINE | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.421 |
| 6 | KEEP | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0006 | 0.8335 | 0.00 | 2.85 | 0.509 |
| 6 | KEEP | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0015 | 0.8143 | 0.00 | 2.85 | 0.502 |
| 6 | KEEP | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0018 | 0.8048 | 0.00 | 2.85 | 0.505 |
| 6 | KEEP | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.501 |
| 6 | COMPACT | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0007 | 0.8279 | 0.00 | 2.85 | 0.505 |
| 6 | COMPACT | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0017 | 0.7933 | 0.00 | 2.85 | 0.505 |
| 6 | COMPACT | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0018 | 0.7954 | 0.00 | 2.85 | 0.508 |
| 6 | COMPACT | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.503 |
| 6 | LINE | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0010 | 0.8375 | 0.00 | 2.85 | 0.488 |
| 6 | LINE | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0019 | 0.8146 | 0.00 | 2.85 | 0.481 |
| 6 | LINE | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0018 | 0.7910 | 0.00 | 2.85 | 0.492 |
| 6 | LINE | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.460 |
| 8 | KEEP | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0009 | 0.8078 | 0.00 | 2.85 | 0.648 |
| 8 | KEEP | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0019 | 0.7727 | 0.00 | 2.85 | 0.642 |
| 8 | KEEP | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0022 | 0.7394 | 0.00 | 2.85 | 0.643 |
| 8 | KEEP | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.639 |
| 8 | COMPACT | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0008 | 0.8052 | 0.00 | 2.85 | 0.642 |
| 8 | COMPACT | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0016 | 0.7699 | 0.00 | 2.85 | 0.646 |
| 8 | COMPACT | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0020 | 0.7865 | 0.00 | 2.85 | 0.640 |
| 8 | COMPACT | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.631 |
| 8 | LINE | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0011 | 0.8375 | 0.00 | 2.85 | 0.550 |
| 8 | LINE | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0019 | 0.8146 | 0.00 | 2.85 | 0.554 |
| 8 | LINE | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0023 | 0.7709 | 0.00 | 2.85 | 0.551 |
| 8 | LINE | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.523 |
| 12 | KEEP | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0008 | 0.8259 | 0.00 | 2.85 | 0.987 |
| 12 | KEEP | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0022 | 0.7911 | 0.00 | 2.85 | 0.983 |
| 12 | KEEP | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0026 | 0.7513 | 0.00 | 2.85 | 0.986 |
| 12 | KEEP | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.974 |
| 12 | COMPACT | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0009 | 0.8052 | 0.00 | 2.85 | 0.974 |
| 12 | COMPACT | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0020 | 0.7681 | 0.00 | 2.85 | 0.970 |
| 12 | COMPACT | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0021 | 0.7458 | 0.00 | 2.85 | 0.972 |
| 12 | COMPACT | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.941 |
| 12 | LINE | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0011 | 0.8238 | 0.00 | 2.85 | 0.687 |
| 12 | LINE | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0021 | 0.7969 | 0.00 | 2.85 | 0.689 |
| 12 | LINE | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0021 | 0.7767 | 0.00 | 2.85 | 0.693 |
| 12 | LINE | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.644 |
| 16 | KEEP | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0011 | 0.8171 | 0.00 | 2.85 | 1.377 |
| 16 | KEEP | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0025 | 0.7855 | 0.00 | 2.85 | 1.377 |
| 16 | KEEP | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0034 | 0.7670 | 0.00 | 2.85 | 1.366 |
| 16 | KEEP | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 1.328 |
| 16 | COMPACT | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0010 | 0.8052 | 0.00 | 2.85 | 1.094 |
| 16 | COMPACT | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0020 | 0.7681 | 0.00 | 2.85 | 1.100 |
| 16 | COMPACT | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0026 | 0.7652 | 0.00 | 2.85 | 1.102 |
| 16 | COMPACT | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 1.065 |
| 16 | LINE | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0010 | 0.8120 | 0.00 | 2.85 | 0.804 |
| 16 | LINE | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0023 | 0.7821 | 0.00 | 2.85 | 0.812 |
| 16 | LINE | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0021 | 0.7909 | 0.00 | 2.85 | 0.809 |
| 16 | LINE | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 0.755 |
| 24 | KEEP | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0011 | 0.8147 | 0.00 | 2.85 | 2.325 |
| 24 | KEEP | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0020 | 0.7786 | 0.00 | 2.85 | 2.459 |
| 24 | KEEP | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0030 | 0.7832 | 0.00 | 2.85 | 2.443 |
| 24 | KEEP | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 2.272 |
| 24 | COMPACT | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0011 | 0.8052 | 0.00 | 2.85 | 1.608 |
| 24 | COMPACT | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0022 | 0.7681 | 0.00 | 2.85 | 1.618 |
| 24 | COMPACT | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0020 | 0.7750 | 0.00 | 2.85 | 1.625 |
| 24 | COMPACT | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 1.518 |
| 24 | LINE | bounded_position | 5 | 1.00 | 1.00 | 0.00 | 0.0012 | 0.8120 | 0.00 | 2.85 | 1.118 |
| 24 | LINE | bounded_velocity | 5 | 1.00 | 1.00 | 0.00 | 0.0019 | 0.7821 | 0.00 | 2.85 | 1.102 |
| 24 | LINE | combined_perturbation | 5 | 1.00 | 1.00 | 0.00 | 0.0022 | 0.7807 | 0.00 | 2.85 | 1.092 |
| 24 | LINE | exact_topology | 5 | 1.00 | 1.00 | 0.00 | 0.0000 | 0.9000 | 0.00 | 2.85 | 1.073 |

There is no topology- or team-size-specific tuning. The result qualifies only
the declared bounded initial-condition envelope and open-space mechanical
controller behavior; it is not a transition or obstacle-passage result.
