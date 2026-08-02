# Phase 6 Neighbour-Discovery Cost Audit

Audit frozen before Phase 6 benchmarks. Phase 5's per-robot graph-construction
growth with bounded graph degree is explained by centralized simulator
orchestration, not by the deployable local graph/model contract.

## Cost ownership

| Stage | Deployable robot-local | Central simulator | Expected scaling |
|---|---|---|---|
| receive and decode already delivered one-hop messages | yes | emulated | O(local messages) |
| discover radio neighbours from all positions | no | `simulate_broadcast_round` / pair scans | O(N^2) aggregate |
| compute global pairwise distances | no | simulator and metrics | O(N^2) |
| build ego-graph tensors | future model adapter, inactive in Phase 6 | batched in Phase 5 benchmark | O(local nodes/edges) after messages exist |
| lookup topology-local offsets | yes | repeated per local input | O(nominal local degree) |
| assemble typed controller input | yes | invoked per robot | O(local peers + local obstacles) |
| base controller | yes | invoked per robot | O(local peers + local obstacles) |
| exact active-set safety projection | yes | invoked per robot | O(m^3) worst case for m local half-spaces |

The deployable Phase 6 adapter accepts a `RobotView` whose neighbour table was
already populated from received beacons and a mission-setup local topology
slice. It never scans a joint state. The qualification simulator separately
measures its global discovery/orchestration loop and the local input/controller
stack. Dense complete communication is reported only as a diagnostic stress
case.

No Phase 4 feature, sensor range or communication protocol is changed to alter
these costs.

## Measured Phase 6 separation

The range-bounded benchmark consumed already formed `RobotView` messages in
the deployable adapter. Median one-hop input degree rose from 4 at N=5 to 16 at
N=24 because a fixed communication radius admits more physically nearby robots
in the larger declared formations. This is range-bounded, but it is not a
constant-degree result. Formation control still selects only registry-declared
formation neighbours; local safety legitimately examines every received
one-hop peer.

| N | one-hop degree | local stack median (ms) | local p95 (ms) | simulator discovery (ms) | simulator aggregate (ms) |
|---:|---:|---:|---:|---:|---:|
| 5 | 4 | 1.318 | 1.603 | 0.260 | 16.493 |
| 6 | 5 | 1.502 | 1.864 | 0.370 | 22.667 |
| 8 | 7 | 1.934 | 2.378 | 0.689 | 38.432 |
| 12 | 11 | 3.078 | 3.465 | 1.636 | 88.057 |
| 16 | 14 | 4.116 | 4.713 | 2.694 | 155.623 |
| 24 | 16 | 5.498 | 7.664 | 5.374 | 328.064 |

The old Phase 5 growth therefore combined at least three effects: centralized
all-position neighbour discovery, centralized per-swarm orchestration, and
larger local message sets under the fixed radio range. Phase 6 does not claim
that the simulator search is deployable. The controller adapter itself has no
joint-state argument and performs no global neighbour scan.
