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
| 9 | **the transition uses `immediate_target_switch`, not the frozen smooth role-space profile** | RB-13R | runtime integration | **OPEN** |

## Defect 9 — the open blocker

The frozen Target V4 contract requires that a changed candidate "must use Phase 7
and the frozen profile". Two execution strategies exist in the frozen code:

    TRANSITION_EXECUTION_STRATEGIES = ('immediate_target_switch',
                                       'generic_role_space_profile')

The publication session swaps the controller's target topology the instant the
node commits — the *immediate* strategy. It does not drive
`transition_execution.RobotLocalTransitionExecutor` along the role-space path
built by `prepare_robot_local_role_space_path`, which is what the smooth profile
means and what keeps robots separated while they exchange grid positions.

Measured consequence, in an open field with **no obstacle involved**: a
COMPACT → LINE reconfiguration on `train-f1-00` at N=6 brings robots 2 and 3 to
**0.3936 m** against the frozen **0.40 m** required clearance, terminating the
rollout with `COLLISION` at control step 25.

Scope of the invalidation:

* **Unaffected** — hold candidates (cases 1 and 3), LINE → COMPACT (case 4,
  which completes and yields a positive), all fixed-topology source policies,
  snapshot/restore, clone isolation, stream matching, and the locality boundary.
* **Not authoritative until fixed** — any Target V4 outcome for a
  COMPACT → LINE candidate, and the collision statistics of any family whose
  source policy performs that transition.

F5 is a partial exception worth stating precisely: its COMPACT → LINE transition
does commit and the run reaches `GOAL_COMPLETE` past both bottlenecks, because
the F5 formation geometry happens not to bring any pair inside the clearance
during the swap. That is luck of geometry, not evidence that the profile is
bound.

`tests/test_phase9c_phase7_live_lifecycle.py::test_case2_compact_to_line_currently_collides_during_reconfiguration`
pins this defect so it cannot be silently forgotten, and instructs its own
replacement once the frozen profile is bound.
