# Reconfiguration Initial Conditions (Task 4R-3)

Implementation `rvt_swarm/decentralized/qualification_fixtures.py` ·
Tests `tests/test_reconfiguration_initial_conditions.py`

---

## 1. Requirement

A KEEP → LINE → KEEP mission must **start inside the nominal KEEP tube**. The
invalidated Task 4 run began at `E_inf^KEEP = 3.018 m` against a 0.55 m
tolerance and then counted the failure to reach a formation it never started in
as a recovery failure.

```
E_inf^KEEP(0) <= epsilon_init = 0.25 m
```

`epsilon_init = 0.25` is **strictly smaller** than `epsilon_form = 0.55`, so an
episode starts comfortably inside the tube rather than on its boundary.

## 2. Initialization

Robots are placed **directly on the persistent KEEP role template**, rotated
into the shared mission frame and translated to the spawn centre, plus a
bounded seeded perturbation of `+/- 0.06 m` per axis. There is no settling
phase, so no settling can be mistaken for recovery.

`simulate_reset_to_fixture` substitutes the environment's procedural spawn for
the duration of the reset and restores it immediately afterwards. It runs once,
before t = 0; it is initialization, not control.

## 3. Validated preconditions

`validate_initial_conditions` checks all of:

| check | threshold | measured (all 3 fixtures, seed 0) |
|---|---|---|
| inside the KEEP tube | `E_inf^KEEP <= 0.25` | **0.0848** |
| no robot-robot collision | `> min_rr_distance = 0.40` | 0.798 |
| no robot-obstacle collision | `> min_ro_distance = 0.55` | 3.16–3.24 (∞ in the open fixture) |
| every robot in bounds | `|p| <= world/2 - r_robot` | pass |
| communication graph connected | one component at `r_comm = 3.0` | pass |

An episode may only be scored if `valid` is true.

## 4. Measured settling time, and why it matters

LINE → KEEP settling from the exact line template in open space takes
**~54 control steps** to re-enter the keep tube (seeds 0/1/2: steps 54, 54, 53;
final error 0.301–0.304). With `L_recover = 20` the mission needs **~74 steps
after the exit plane**, i.e. roughly 10 m of downstream travel.

This is a measured property of the controller, taken **before** the probe set
was run, and it is what sizes the fixture world (`FIXTURE_WORLD_SIZE = 18.0`).
It is not a tuning knob and was not adjusted to change any probe's outcome.
