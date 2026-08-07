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


---

# Resolution (owner decision 1): mission-staged transition

The owner froze staging. Implemented as `rvt_swarm/phase9c_rb/staging.py`.

## Derived threshold, no new constant

    v_settle = a_max * dt = 0.6 m/s^2 * 0.15 s = 0.09 m/s

read from the authoritative runtime configuration and never written as a
literal (asserted by an AST test that rejects any float literal in the module).
A robot is MOTION_SETTLED when `||v_i|| <= v_settle` -- the speed the frozen
acceleration bound can remove within one frozen control interval. No scaling
coefficient, epsilon or tuning factor.

## How the goal term is suppressed

The frozen controller computes `base = formation + goal + damping + obstacle` as
a plain sum *before* the safety projection. Staging therefore subtracts the
already-separated `goal_term` from `base_action`, giving exactly `0 * u_goal`,
and reapplies the unchanged projection. No Phase 6 equation is rewritten and no
gain is touched. Formation/transition tracking, damping, obstacle response,
safety and the normal dynamics all remain active; simulator time continues;
velocity is never zeroed; there is no global pause.

## Qualification results

| binding | min pair separation | outcome |
|---|---:|---|
| immediate target switch | 0.3936 m | COLLISION |
| frozen profile, asserted readiness | 0.3979 m | COLLISION |
| frozen profile, real readiness | 0.3979 m | COLLISION |
| **+ mission staging, COMPACT -> LINE** | **0.4244 m** | **GOAL_COMPLETE** |
| **+ mission staging, LINE -> COMPACT** | **0.6507 m** | **GOAL_COMPLETE** |
| frozen Phase 7R rest reference | 0.5247 m | no collision |

COMPACT -> LINE milestones: staging starts at t=1.80 s from speeds 0.58-0.67
m/s; robots settle at t=4.65-5.25 s; confirmation 5.25 s; profile execution
5.40 s; target dwell 10.65 s; COMPLETE 13.65 s; GOAL_COMPLETE at step 173.

## Time cost

Staging is not free and is not compensated. A staged transition episode takes
173 control steps against 95 for a fixed-topology hold on the same layout --
deceleration, profile execution and the 3.0 s dwell all count toward mission
duration, episode horizon and timeout metrics. The clock is never suspended.
