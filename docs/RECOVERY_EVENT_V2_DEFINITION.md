# Recovery Event V2 — Definition (Tasks 1–4)

Implementation: `rvt_swarm/recovery_v2.py`, `rvt_swarm/regions.py`
Tests: `tests/test_recovery_event_v2.py` (16 tests)

V1 conflated three different things into one 14-step label and consequently fired
on **27.8 %** of rollouts in corridors no robot can physically enter. Here they are
three distinct events, and only the third is a candidate paper target.

## 0. Notation

| Symbol | Meaning |
|---|---|
| `x` | decision state (positions, velocities, obstacles, goal, latent formation state) |
| `τ ∈ T` | candidate mode, `T = {keep, line, split}` |
| `π_e(·, m)` | shared heuristic expert acting under mode `m` |
| `H_commit` | commitment duration (steps) |
| `T_max` | maximum rollout length (steps) |
| `ε_tube` | `tube_scale · formation_tolerance` |
| `L` | required consecutive in-tube dwell |
| `c_k` | team centroid at step `k` |
| `x_exit` | exit plane of the constricting structure (§4) |

## 1. A — Local progress event *(diagnostic only)*

```
Y_local(x, τ) = 1  iff  over the first H_local = 14 steps
                       Δprogress ≥ p_min  OR  form_rms decreased
```

**This is a short-horizon diagnostic. It is never called recovery or
recoverability**, and it is never a training target. It exists so that "the team
improved locally" can be *measured* and then shown to be insufficient.

## 2. B — Formation recovery event

```
Y_form(x, τ) = 1  iff  ∃ a window of L consecutive steps with form_rms < ε_tube
                   AND no robot–robot collision
                   AND no robot–obstacle collision
                   AND no deadlock
                   AND no irreversible collapse
```

**Says nothing about task completion.** A team can hold formation perfectly while
going nowhere; `test_temporary_formation_recovery_then_failure` asserts exactly
that case occurs, which is what makes B and C different measurements rather than
one measurement under two names.

## 3. C — Task-recovery event *(GOLD STANDARD)*

```
Y_task(x, τ) = 1  iff  completion(x, τ)
                   AND no robot–robot collision on [0, T_end]
                   AND no robot–obstacle collision on [0, T_end]
                   AND no deadlock
                   AND no irreversible collapse
                   AND ∃ a window of L consecutive steps with form_rms < ε_tube

completion(x, τ) =  goal_reached                       if the scenario has no bottleneck
                    goal_reached ∧ crossed_exit        if it has one
crossed_exit     =  ∃ k ≤ T_end : c_k,x > x_exit
```

The `crossed_exit` conjunct is what repairs V1: `x_exit` lies beyond **every**
obstacle of the constricting structure, so a centroid past it cannot have arrived
without traversing. Approaching a wall can no longer qualify.

## 4. Geometric regions

`regions_for(obstacles, goal, cfg, start_x)` finds the densest x-band of obstacles
strictly between start and goal, requires ≥ 3 tiles, and sets

```
x_entrance = min_x(structure) − (R_obs + d_ro)
x_exit     = max_x(structure) + (R_obs + d_ro)
x_downstream = x_exit + ½(R_obs + d_ro)
```

Sparse clutter (< 3 tiles in any band) yields `has_bottleneck = False`, and then
`completion` reduces to `goal_reached` — an open field is not asked to cross
anything. A structure *behind* the start is excluded by construction, so standing
still can never register as a crossing.

## 5. The candidate-mode intervention (Task 2)

A fair per-mode label requires candidates to differ **only** in the decision being
evaluated.

| Element | Value |
|---|---|
| State | `x`, cloned; identical for every candidate |
| Commitment | mode `τ` held for `H_commit` steps |
| Action policy during commitment | `π_e(·, τ)` |
| **Continuation policy after commitment** | **`π_e(·, keep)` — identical for every candidate** |
| Horizon | `T_max` |
| Perturbations | initial position σ = 0.02 m, action σ = 0.03 m/s²; the only stochasticity |
| Termination | goal · collision · deadlock · collapse · `T_max` |

**The oracle is never given a privileged continuation for the candidate it
prefers.** `CONTINUATION_MODE = 0` is a module constant, and
`test_continuation_policy_is_identical_across_candidate_modes` asserts the
single line of code that could break this property.

### Two interventions compared

| | Definition | Interpretation |
|---|---|---|
| **A — fixed commitment** *(preferred)* | hold `τ` for `H_commit`, then the common continuation | the **causal effect of the decision**, not of the whole trajectory |
| B — full mode | hold `τ` for the entire rollout | confounds the decision with a policy that no selector would execute |

A is preferred because a runtime selector re-decides periodically; holding one
mode for 240 steps measures a policy nobody deploys.

## 6. Predeclared grids

```
H_commit ∈ {5, 10, 20}          T_max ∈ {60, 120, 240}
tube_scale ∈ {0.75, 1.0, 1.5}   L ∈ {1, 3, 5}      perturb_pos ∈ {0.02, 0.05}
```

Default: `H_commit = 10, T_max = 120, tube_scale = 1.0, L = 3, perturb = 0.02`.
Values are **not** selected by learned-model performance — no learned model exists
in this task.

## 7. Recorded per rollout (Task 3)

`local_progress`, `formation_recovery`, `task_recovery`, `task_completed`,
`rr_collision_steps`, `ro_collision_steps`, `deadlock`, `irreversible_collapse`,
`tube_entry_time`, `tube_dwell_max`, `goal_progress`, `crossed_bottleneck`,
`reached_downstream`, `terminal_reason`, `rollout_duration`.

## 8. The shaped rollout utility is not this

`recoverability.py::rollout_score` averages eight normalised terms and can trade a
collision against progress. It is a **utility**, and it is called that everywhere
from now on. It may be *evaluated* as a surrogate predictor of `Y_task` (Task 7),
but it is not the target.

## 9. Immediate empirical contrast

| family | V1 "recovered" | V2 local | V2 formation | **V2 task** |
|---|---|---|---|---|
| `infeasible` (0.80–0.95 m gate) | **0.667** | 0.861 | 0.472 | **0.000** |
| `keep_open` | 0.667 | 0.861 | 1.000 | **1.000** |
| `line_corridor` | 0.667 | 0.833 | 0.741 | **0.574** |

**V1 returned 0.667 for all three** — it could not distinguish an impassable
corridor from an open field. V2 separates them completely, and the three concepts
are demonstrably different quantities rather than one quantity renamed.
