# Phase 8E-MC — Transition/Mission Coupling Audit

Specification-only. No dataset row, no training, no final-test access, no
Study A N=24 access. No code changed in this phase.

## MC-2 — frame audit: the binding is correct

`RobotLocalRoleSpacePath.intermediate_topology(progress)` interpolates **role
offsets** and emits, for each formation neighbour,

    desired_offset_from_observer_meters = peer_offset - own_offset

`RobotLocalTransitionExecutor.build_input` substitutes that slice into the
frozen controller input. Because every quantity the controller consumes is a
**pairwise difference**, a uniform world translation cancels exactly. The
profile is therefore translation-invariant **by construction**, and the
publication adapter does not anchor it to a static world origin.

The empirical discriminator, `train-f1-00` at N=6, identical positions, goal and
obstacles, changing only the velocity field:

| variation | min pair separation | outcome |
|---|---:|---|
| baseline, cruising (warmup 12) | 0.3979 m | COLLISION |
| **same positions, velocity zeroed** | **0.4166 m** | GOAL_COMPLETE |
| warmup 30, velocity zeroed | 0.4176 m | GOAL_COMPLETE |

Zeroing velocity while holding position, goal and obstacles fixed removes the
breach. A frame error would be position-dependent; this is velocity-dependent.

**Conclusion: MC-2 does not resolve the discrepancy as a binding bug. The frame
composition is already correct, and the 0.3979 m breach is genuine coupling
between mission translation and the at-rest-qualified transition profile.**

## MC-5 — no existing motion-settle tolerance exists

MC-3 mission staging requires a `MOTION_SETTLED` predicate, and MC-5 forbids
inventing a threshold: an existing frozen tolerance must be reused.

An exhaustive search of the runtime configuration and of the Phase 6, Phase 7,
readiness and qualification modules found **no velocity or settling tolerance**.
Every speed-related frozen constant is a *bound*, not a settle criterion:

| candidate | value | why it does not serve |
|---|---:|---|
| `physical.maximum_speed_meters_per_second` | 0.9 | an upper bound on speed |
| `physical.maximum_acceleration_...` | 0.6 | an upper bound on action |
| `formation.spacing_margin_meters` | 0.05 | a spatial margin, metres |
| `derived.formation_tolerance_meters` | 0.55 | Metric V3 spatial tube, metres |
| `safety.inter_robot_safety_margin_meters` | 0.04 | spatial, metres |
| `controller.progress_window_seconds` | 0.75 | a progress window, seconds |
| readiness `dynamics_margin` | derived | `max_speed - speed`, a headroom quantity |

None is a velocity at which motion counts as settled, and none carries prior
scientific use as one. Reusing a spatial margin as a speed threshold would be
inventing a constant with a unit change.

**MC-5 therefore triggers its own stop condition: "If no scientifically
appropriate existing tolerance exists: STOP with Verdict A. Do not choose a new
number in this phase."**

## What remains unspecified

Exactly one scientific choice, and it is the protocol owner's:

1. **Concurrent execution.** If transitions are intended to run while the
   mission translation term is active, the frozen Phase 7R qualification and the
   readiness envelope are incomplete — they certify SAFE with positive margins
   (0.098–0.191 m) while closed-loop swept paths breach 0.4000 m by ~3 mm.
2. **Staged execution.** If the mission is intended to pause locally during a
   transition, a `MOTION_SETTLED` tolerance must be frozen, and no existing
   constant supplies it.

Both readings are defensible; each implies a different runtime and a different
time cost for the online method. Nothing in this phase chooses between them.
