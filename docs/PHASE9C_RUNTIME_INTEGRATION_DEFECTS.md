# Phase 9C-RB Runtime Integration Defects

Every item below is a **runtime integration defect** — a fault in the adapter
layer that binds frozen scientific modules together. **None** is a scientific
protocol change, and none was fixed by retuning a scientific constant. No
geometry, speed, horizon, controller gain, safety semantic, transition profile,
Metric V3 definition, budget, seed or split was altered to resolve any of them.

| # | defect | discovered by | classification | status |
|---|---|---|---|---|
| 1 | `S2.initial_topology_override` was never consulted, so S2 ran COMPACT instead of LINE | RB-18F5 gate | runtime integration | fixed |
| 2 | F9 obstacles entered the controller twice — once via `RobotView.obstacles` with the static convention, once correctly | RB-B | runtime integration | fixed |
| 3 | dynamic relative velocity used `-v_robot` instead of `v_obstacle - v_robot` | RB-B | runtime integration | fixed |
| 4 | the session always used `DEFAULT_RUNTIME_CONFIG` (team_size 6), so the frozen protocol node raised for every other N | RB-A | runtime integration | fixed |
| 5 | the Metric V3 dwell clock was never tracked; the predicate read a key nothing set | RB-14 | runtime integration | fixed |
| 6 | the originator never called `adopt_intent` on itself, so every lifecycle stayed in `STABLE_TOPOLOGY` | F5-R | runtime integration | fixed |
| 7 | score / readiness / confirmation used tokens outside the frozen vocabulary | F5-R | runtime integration | fixed |
| 8 | `accept_confirmation` records unanimity but `commit()` was never called, so `TOPOLOGY_COMMITTED` was never entered | F5-R | runtime integration | fixed |
| 9 | the transition used `immediate_target_switch`, not the frozen role-space profile | RB-13R | runtime integration | **fixed** |
| 10 | **readiness is hardcoded `SAFE`, so the frozen readiness certificate never gates commitment** | D9-5 | runtime integration | **OPEN** |

## Defect 9 — fixed

`RobotLocalTransitionExecutor` is now bound. On commit each robot builds its own
executor from `prepare_robot_local_role_space_path` and
`derive_transition_motion_profile`, and the frozen executor supplies the local
intermediate target until the frozen completion semantics retire it. Its
`build_input`/`evaluate` interface is identical to the forced-topology adapter,
so it drops in without restating any interpolation, displacement or progress
law in this package.

Measured effect on the open-space COMPACT -> LINE regression at N=6:

| binding | minimum pair separation | outcome |
|---|---:|---|
| immediate target switch | 0.3936 m | COLLISION |
| **frozen role-space profile** | **0.3979 m** | **still COLLISION** |
| frozen Phase 7R fixture, same profile | **0.5247 m** | no collision |

The profile is sound — the frozen Phase 7R fixture clears 0.4000 m comfortably.
Binding it improved separation but did not resolve the breach, which pointed at
a second gap.

## Defect 10 — the open blocker

`advance_transition_lifecycle` emits `readiness_message("SAFE", 0.0, now)`
unconditionally. The frozen
`StrictTransitionRuntime.local_readiness_certificates` instead *computes* each
robot's readiness from positions, velocities, source and target topology, goal
origin, mission direction and local obstacles.

Readiness is the gate that decides whether a transition may commit at all. By
asserting it, the publication session commits transitions the frozen certificate
would have refused, and the profile then executes from a formation whose
accumulated error has already eaten the clearance margin. That is why the
frozen fixture — which starts from an exact source formation and computes real
readiness — reaches 0.5247 m while the session reaches 0.3979 m.

Until readiness is computed, any changed-topology candidate outcome remains
non-authoritative, exactly as defect 9 required.

## F5 after the profile binding (D9-10 re-run)

| milestone | step | t (s) | progress (m) |
|---|---:|---:|---:|
| event originated, intent adopted | 0 | 0.00 | — |
| score agreement | 1 | 0.15 | -0.01 |
| all-ready agreement | 2 | 0.30 | 0.01 |
| confirmation | 3 | 0.45 | 0.04 |
| commit + profile start | 4 | 0.60 | 0.08 |
| target tube entry (`TARGET_DWELL`) | 84 | 12.60 | 9.52 |
| GOAL_COMPLETE | 99 | 14.85 | 11.46 |

Profile progress reaches 1.0 for every robot. Both bottlenecks (2.00-3.50 and
6.50-8.00) are passed. The LINE dwell reaches 2.4 s of the required 3.0 s before
the mission ends, so the lifecycle does not reach `COMPLETE` — a legitimate
Target V4 negative, not a binding defect. Tube entry moved from step 36 to step
84, which is the real cost of the frozen motion law.
