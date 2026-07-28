# Episode Metric Specification

Audit and specification of every metric returned by the evaluator.
**Written before implementation**, so that definitions are proposed explicitly
rather than changed silently.

Companion test: `tests/test_all_episode_metrics.py`.
Implementation: `rvt_swarm/metrics.py` (`EpisodeAccumulator`).

## Semantics codes

| Code | Meaning |
|---|---|
| **A** | terminal-state metric — value at the final timestep |
| **B** | episode-wide conjunction — true only if true at every step |
| **C** | episode-wide event latch — true if true at *any* step |
| **D** | episode-wide count |
| **E** | episode-wide minimum or maximum |
| **F** | time average over steps |
| **G** | percentage of episode time |
| **H** | first-passage time |

## Audit table

`compute_metrics()` (`rvt_swarm/environment.py:522-560`) is evaluated on the
*current* state and carries no history, so **every** value it produces is
semantics **A** unless the evaluator aggregates it.

| Metric | Current implementation | Current semantics | Intended scientific semantics | Correct aggregation | Code change required | Unit test required |
|---|---|---|---|---|---|---|
| `goal_reached` | `d_goal < goal_tolerance` at terminal step | A | **C** event latch | OR over steps | yes (latch) | yes |
| `collision_free` | conjunction over steps *(fixed in previous commit)* | B | **B** | AND over steps | done | yes |
| `rr_collision` | mean over robot pairs of `d < min_rr`, terminal | A | A, retained as an instantaneous density | keep + expose terminal | rename-preserve | yes |
| `ro_collision` | mean over robot–obstacle pairs, terminal | A | A, retained | keep + expose terminal | rename-preserve | yes |
| `robot_robot_collision_steps` | **absent** | — | **D** count of steps with ≥1 robot–robot collision | sum of indicators | yes (new) | yes |
| `robot_obstacle_collision_steps` | **absent** | — | **D** | sum of indicators | yes (new) | yes |
| `min_rr_clearance` | **absent** | — | **E** episode minimum | min over steps | yes (new) | yes |
| `min_ro_clearance` | **absent** | — | **E** episode minimum | min over steps | yes (new) | yes |
| `form_ok` | `form_rms < tol` at terminal step | A | **A** — deliberately kept terminal | unchanged | no | yes |
| `time_in_formation_tube` | **absent** | — | **G** fraction of steps inside the tube | mean of indicator | yes (new) | yes |
| `form_rms` | terminal RMS formation error | A | **A** retained | unchanged | no | yes |
| `form_rms_mean` | **absent** | — | **F** | mean over steps | yes (new) | yes |
| `form_rms_max` | **absent** | — | **E** | max over steps | yes (new) | yes |
| `deadlock` | terminal flag from `stall_counter` | A | **C** event latch | OR over steps | yes (latch) | yes |
| `stall_rate` | `stall_counter / step_count` at terminal | F (approx.) | **F** time average of no-progress steps | mean of indicator | yes (recompute) | yes |
| `irreversible_collapse` | terminal flag | A | **C** event latch | OR over steps | yes (latch) | yes |
| `success` | conjunction *(fixed in previous commit)* | B | **B** | latched goal ∧ episode collision-free ∧ terminal `form_ok` | done | yes |
| `completion_time` | `steps` = episode length | D | **H** first-passage time to the goal | index of first goal-reach; censored otherwise | yes (new) | yes |
| `topology_switches` | cumulative counter read at terminal | D | **D** | already correct | no (verify) | yes |
| `formation_scale_motion` | cumulative sum read at terminal | D | **D** | already correct | no (verify) | yes |
| `safety_filter_activations` | **absent — never recorded** | — | **D** count of steps where the filter modified the action | sum of indicators | yes (instrument) | yes |
| `safety_filter_activation_rate` | **absent** | — | **G** | activations / steps | yes (new) | yes |
| `ms_per_step` | wall-clock incl. checkpoint load | F | **F**, excluding I/O | mean, model preloaded | out of scope here | no |

## Definition changes (explicit, not silent)

Three metrics change meaning. Each keeps its previous value under an explicit
`*_terminal` key so both conventions remain reportable and comparable.

### 1. `goal_reached`: terminal → event latch

*Previously:* the team's centroid is within `goal_tolerance` **at the final step**.
*Now:* the centroid came within `goal_tolerance` **at any step**.

In practice these coincide, because `step()` sets `done = goal_reached or
step_count >= max_steps` (`environment.py:519`), so an episode terminates on the
first goal contact. The latch is implemented for robustness (it stops being
equivalent the moment the termination rule changes) and its equivalence under the
current rule is asserted by test.
**Expected numerical impact: none.** Retained: `goal_reached_terminal`.

### 2. `deadlock`: terminal condition → event latch

*Previously:* at the final step, `stall_counter * v_max * dt >= max(goal_tolerance,
nominal_spacing)` and the goal is not reached.
*Now:* that condition held at **any** step of the episode.

`stall_counter` decrements when progress resumes (`environment.py:490-493`), so
a team that stalls, recovers, and finishes was previously recorded as
deadlock-free. Whether that is desirable is a modelling choice, so **both are
reported**: `deadlock` (latch) and `deadlock_terminal` (previous definition).
**Expected numerical impact: deadlock rates increase.** The paper's numbers used
the terminal definition; any comparison must state which is used.

### 3. `irreversible_collapse`: terminal → event latch

*Previously:* the collapse predicate held at the final step.
*Now:* it held at any step. "Irreversible" is only meaningful as a latch — under
the terminal definition a state described as irreversible could be, and was,
escaped.
**Expected numerical impact: collapse rates increase.** Retained:
`irreversible_collapse_terminal`.

## Deliberately unchanged

- **`form_ok` stays a terminal flag** and remains the formation term inside
  `success`. Changing the success criterion would alter the headline metric's
  definition, which is a scientific decision for the authors, not a bug fix.
  `time_in_formation_tube` (**G**) is added *alongside* it so formation quality is
  no longer represented by a single final-step flag, as the audit requires.
- **`rr_collision` / `ro_collision` remain instantaneous pair densities.** They are
  not counts and never were; the new `*_collision_steps` counters supply the count
  semantics without redefining the existing keys.
- **`stall_rate`** keeps its name but is recomputed as an honest time average of a
  no-progress indicator derived from the `goal_distance` sequence, rather than
  from the self-decrementing `stall_counter`. Previous value:
  `stall_rate_terminal`.

## Derived quantities

- **no-progress indicator**: `goal_distance[k] >= goal_distance[k-1]`, derived from
  the reported `goal_distance` sequence. Requires no environment change.
- **first-passage completion time**: `first_goal_step * dt`, or `None` (censored)
  when the goal is never reached. Reporting a mean over censored episodes is
  invalid; report the reach rate and the mean over reaching episodes separately.

## Schema version

Every result row produced under this specification carries
`evaluation_schema_version = 2` (`rvt_swarm/metrics.py`). Version 1 denotes the
pre-correction semantics. Aggregation refuses to mix versions — see
`docs/EVALUATION_PROTOCOL_V2_VERIFICATION.md` and
`results/legacy_pre_metric_fix/README.md`.
