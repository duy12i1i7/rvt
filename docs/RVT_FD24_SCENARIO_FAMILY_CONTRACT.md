# RVT-FD24 Scenario Family Contract

The authoritative code schema is `rvt-scenario-family/v1`; deterministic layout
descriptors use `rvt-scenario-layout/v1`. Every family starts in COMPACT,
supports `N={5,6,8,12,16,24}`, uses frozen physical/controller/safety/Metric V3
semantics and terminates at the listed horizon.

| ID | family | purpose/headroom | geometry range | transitions | communication | horizon |
|---|---|---|---|---|---|---:|
| F1 | OPEN_NOMINAL_TRANSIT | nominal transit; BOTH_SUCCESS | sparse offset 3.0-3.9 m | none required | nominal | 90 s |
| F2 | STRAIGHT_NARROW_PASSAGE | clear LINE_ONLY | width 1.30-1.55 m, length 4.0-5.2 m | C->L->C | nominal | 120 s |
| F3 | OFFSET_ENTRY_PASSAGE | offset-entry LINE_ONLY | offset 0.7-1.4 m, width 1.35-1.60 m | C->L->C | nominal | 135 s |
| F4 | CURVED_OR_S_SHAPED_PASSAGE | sustained narrow LINE_ONLY | amplitude 0.7-1.4 m, width 1.40-1.65 m | C->L->C | nominal | 150 s |
| F5 | SEQUENTIAL_BOTTLENECKS | RECONFIGURATION_REQUIRED | separation 3.0-4.8 m, width 1.40-1.65 m | repeated C->L->C | nominal | 180 s |
| F6 | FALSE_BOTTLENECK_OR_FEASIBLE_BYPASS | COMPACT_ONLY or BOTH_SUCCESS | turn radius 1.0-1.8 m, clearance 1.2-2.0 m | optional C->L | nominal | 130 s |
| F7 | TOPOLOGY_NEUTRAL_CLUTTER | BOTH_SUCCESS, no winner label | clearance 2.8-3.8 m | optional either direction | nominal | 110 s |
| F8 | COMMUNICATION_DEGRADED_RECONFIGURATION | RECONFIGURATION_REQUIRED with agreement stress | delay 0-0.30 s, loss 0-0.15 | C->L->C | bounded loss/delay or restored disconnection | 180 s |
| F9 | DYNAMIC_LOCAL_OBSTACLE | BOTH_SUCCESS or LINE_ONLY | speed 0.15-0.35 m/s, crossing 12-24 s | optional either direction | nominal | 150 s |
| F10 | DIAGNOSTICALLY_INFEASIBLE | BOTH_FAIL | width 0.65-0.95 m | attempted C->L | nominal | 90 s |

Obstacle representations are immutable circles, finite corridor wall segments,
polyline corridor boundaries, explicit bypass branches and timestamped dynamic
waypoints. The goal is reached only after the goal region and required final
Metric V3 dwell are complete. Communication schedules are part of the episode
identity and are matched across compared methods.

All families require finite non-self-intersecting geometry, physically valid
initial roles, in-bounds goal/obstacles and a declared communication contract.
Duplicate geometry/parameter tuples, initial collisions, unintended unreachable
goals and metric/simulator invalidity are excluded with published reasons.
Qualification uses always COMPACT, always LINE and the frozen scripted
COMPACT/LINE transition oracle. No family is required to favour learning.
