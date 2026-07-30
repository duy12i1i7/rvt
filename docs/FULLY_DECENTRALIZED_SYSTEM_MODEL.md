# Fully Decentralized System Model

Formal system definition for the leaderless keep/line formation-mode selector.

**Single source of truth:** `rvt_swarm/decentralized/system_model.py`.
Every parameter, permitted source, prohibited source and link assumption in this
document is transcribed from that module (plus `rvt_swarm/decentralized/roles.py`
for the formation geometry). Where a number appears here it was either read from
the code or computed by running the code; the computation is reproduced in
§10 so it can be re-run and the document and the code cannot silently drift.

Status at time of writing: **specification only**. Nothing in §11 has been
measured yet. See §9 for the explicit list of what is *not* proven.

---

## 1. Entities, modes, timing

| Symbol | Meaning | Value / source |
|---|---|---|
| `V` | robot set, `|V| = N` | `N in {4, 6}` in the current experiment grid |
| `i, j` | persistent robot identifiers | `RobotView.robot_id`, immutable for the mission |
| `tau` | formation mode | `tau in MODES = (KEEP, LINE) = (0, 2)`; split (`1`) is removed |
| `t` | control step index | integer; wall-clock `t * T_ctrl` |
| `T_ctrl` | control period | `CommParams.t_ctrl = 0.15 s` (= `EnvConfig.dt`) |
| `T_comm` | communication period | `CommParams.t_comm = 0.15 s`, one beacon per control step |

`MODE_NAME = {0: "keep", 2: "line"}`. The mode integers are *not* renumbered to
`{0, 1}`: the gap at `1` is the removed split mode and keeping the gap makes any
accidental re-introduction of split a loud `ValueError` in
`RoleAssignment.coords`, not a silent relabelling.

---

## 2. Robot state

The complete locally-available state of robot `i` at step `t`:

```
x_i^t = [ p_i^t, v_i^t, r_i^keep, r_i^line, tau_i^t, e_i^t, s_i^t, g_i^t, m_i^t, O_i^t, N_i^t ]
```

This is exactly the field list of `system_model.RobotView`, which is a **closed
container**: if a quantity is not a field of `RobotView`, no deployable function
can obtain it.

| Component | `RobotView` field | Type | Source | Permitted-source class |
|---|---|---|---|---|
| `p_i^t` — own position | `position` | `Tuple[float, float]` | own localisation, in the shared frame | `self_state` |
| `v_i^t` — own velocity | `velocity` | `Tuple[float, float]` | own odometry | `self_state` |
| `i` — persistent ID | `robot_id` | `int` | burned in at mission configuration | `self_id_and_role` |
| `r_i^keep` — keep role coord | `role_keep` | `Tuple[float, float]` | `RoleAssignment.keep[i]`, template frame, fixed before `t = 0` | `self_id_and_role` |
| `r_i^line` — line role coord | `role_line` | `Tuple[float, float]` | `RoleAssignment.line[i]`, template frame, fixed before `t = 0` | `self_id_and_role` |
| `tau_i^t` — committed mode | `committed_mode` | `int in MODES` | own commit logic | `committed_mode`, `local_memory` |
| `e_i^t` — epoch counter | `epoch_id` | `int` | own counter, reconciled by max-consensus over messages | `local_memory` |
| `s_i^t` — steps since last decision | `steps_since_decision` | `int` | own counter | `local_memory` |
| `g_i^t` — local progress diagnostic | `local_progress` | `float` | robot-local, computed from own `p_i` and the shared mission direction | `self_state` + `shared_goal` |
| `goal` | `goal` | `Tuple[float, float]` | shared mission constant, identical on all robots | `shared_goal` |
| `psi_mission` — mission direction | `mission_dir` | `Tuple[float, float]` | shared mission constant (`corridor_dx`, `corridor_dy`) | `shared_frame`, `shared_goal` |
| `O_i^t` — self-sensed obstacles | `obstacles` | `Sequence[Tuple[float, float, float]]` | own lidar, within `R_obs` | `local_obstacles` |
| `N_i^t` — one-hop neighbour table | `neighbours` | `Sequence[NeighbourRecord]` | received messages only (§4) | `one_hop_messages` |

Two derived helpers on `RobotView` are pure functions of the table and add no
information: `neighbour_ids()` and `degree` (`= |N_i^t|`).

Model and controller parameters (`model_parameters`, `controller_parameters`) are
common offline-trained/offline-tuned constants. They are identical on every
robot and are loaded before `t = 0`, so they are state of the *fleet
configuration*, not of the joint runtime state.

### 2.1 Neighbour record — ego-relative by construction

`NeighbourRecord` is what robot `i` retains about neighbour `j`:

| Component | Field | Note |
|---|---|---|
| `j` | `robot_id` | persistent ID of the sender |
| `p_j - p_i` | `rel_position` | **relative only.** `p_j` never appears in a deployable structure |
| `v_j - v_i` | `rel_velocity` | relative only |
| `r_j^keep`, `r_j^line` | `role_keep`, `role_line` | template-frame role coordinates, communicated by `j` |
| `tau_j` | `committed_mode` | `j`'s committed mode as of its last message |
| `e_j` | `epoch_id` | `j`'s epoch counter |
| message age | `message_age_steps` | in control steps; gates staleness (§4) |
| `deg(j)` | `degree` | `j`'s own neighbour count, communicated by `j`; required for the Metropolis–Hastings weights |
| link health | `link_valid`, `packet_loss_estimate` | locally estimated |

`NeighbourRecord.distance` is `||rel_position||`, a derived scalar.

**The absolute-position rule.** Robot `i` knows `p_i` (its own state) and knows
`p_j - p_i` for `j in N_i` (measured/communicated relative quantity). It could in
principle add them. The contract forbids materialising that sum: no deployable
structure or feature may hold a neighbour's absolute position. `NeighbourRecord`
enforces this by *not having a field for it*. Formation geometry is expressed
pairwise (`roles.pairwise_offset`), so no deployable computation ever needs it.

---

## 3. Graphs

Let `p_i^t` be the true position of robot `i` at step `t`.

### 3.1 Communication graph

```
G_c^t = (V, E_c^t)
E_c^t = { (i, j) in V x V : i != j  and  || p_i^t - p_j^t || <= R_comm }
```

with `R_comm = CommParams.r_comm = 3.0 m`. `E_c^t` is recomputed every
communication period; robots enter and leave `R_comm` as the formation deforms
(`LINK_ASSUMPTIONS["time_varying"]`). Nominally symmetric, so `E_c^t` is an
undirected graph (§5).

`E_c^t` is the *link* graph. The *delivered-message* graph is a subgraph of it
after independent per-direction packet loss and delivery latency are applied; it
can be transiently directed even though the link graph is symmetric
(`LINK_ASSUMPTIONS["directed"]`).

### 3.2 Sensing graph

```
G_s^t = (V, E_s^t)
E_s^t = { (i, j) : i != j  and  || p_i^t - p_j^t || <= R_sense },   R_sense = 4.0 m
```

**The sensing graph is deliberately not used to build the neighbour set.**
`CommParams.r_sense` is retained so the assumption is explicit and auditable, but
in the nominal configuration `N_i^t` is populated from communication only. Since
`R_sense = 4.0 > R_comm = 3.0`, using sensing would strictly enlarge the
neighbour set; the stricter and more testable choice is taken instead.

### 3.3 Obstacle observation set

```
O_i^t = { obstacle o : || p_i^t - p_o^t || <= R_obs },   R_obs = 3.0 m
```

`R_obs = 3.0 m` equals `EnvConfig.lidar_range`, so the decentralized obstacle
view is exactly what the robot's own sensor sees. The full obstacle array
(`obs["obstacles"]`) is unbounded by sensor range and is prohibited (§7.2).

### 3.4 One-hop neighbour set — the operative definition

`N_i^t` requires **both** conditions:

```
N_i^t = { j != i :  (i, j) in E_c^t                              [range condition]
                    and  age_ij^t <= Delta_stale }               [staleness condition]

age_ij^t = t - (step index of the newest message from j held by i)
Delta_stale = CommParams.delta_stale_steps = 3 control steps = 0.45 s
```

The range condition is a property of the physical link at time `t`. The
staleness condition is a property of robot `i`'s *table*: a neighbour that is in
range but whose newest message is older than `Delta_stale` — because of loss or
delay — is marked stale and excluded. A delayed message is accepted only while
its age is still `<= Delta_stale` (`LINK_ASSUMPTIONS["delayed"]`).

Consequence: `N_i^t` is what robot `i` can actually justify believing, not what
an omniscient observer would compute from `E_c^t`. Under loss, `N_i^t` can be a
strict subset of `i`'s neighbours in `G_c^t`, and `j in N_i^t` does not imply
`i in N_j^t` even under symmetric links.

`RobotView.degree = |N_i^t|` is therefore the *effective* degree, and it is that
effective degree which enters the consensus weights.

---

## 4. Parameter table

| Parameter | Code symbol | Value | Units | Justification |
|---|---|---|---|---|
| `R_comm` | `CommParams.r_comm` | 3.0 | m | See §4.1 — chosen so line is multi-hop and keep is one-hop complete. |
| `R_sense` | `CommParams.r_sense` | 4.0 | m | Matches `EnvConfig.sensing_radius = 4.0`. Declared but *not* used to populate `N_i`; retained so the unused capability is explicit and auditable rather than silently available. |
| `R_obs` | `CommParams.r_obs` | 3.0 | m | Exactly `EnvConfig.lidar_range = 3.0`, so the decentralized obstacle view equals what the robot's own sensor physically returns. No obstacle enters a feature that the robot could not have seen. |
| `Delta_stale` | `CommParams.delta_stale_steps` | 3 | control steps (= 0.45 s at `T_ctrl = 0.15`) | At `EnvConfig.max_speed = 0.9 m/s` a neighbour can move at most `0.9 * 0.45 = 0.405 m` inside the staleness window, well inside `nominal_spacing = 0.9 m`. So a message accepted at the staleness limit still describes a neighbour within half a formation spacing of where it was reported. |
| `T_comm` | `CommParams.t_comm` | 0.15 | s | One beacon per control step in the nominal configuration; equal to `EnvConfig.dt`, so communication is not implicitly faster than control. |
| `T_ctrl` | `CommParams.t_ctrl` | 0.15 | s | Exactly the simulator step `EnvConfig.dt = 0.15`. The decentralized loop runs at the same rate as the environment it is evaluated in; no sub-step cheating. |
| `K_score` | `ConsensusParams.k_score` | 4 | consensus rounds per decision epoch | Number of finite rounds of score averaging. Selected on **validation layouts only** from the predeclared grid `K_SCORE_GRID = (0, 1, 2, 3, 4, 6)`, which is frozen in code before any run so the choice cannot be rationalised after seeing results. The binding constraint: the `N=6` line graph has diameter 2 (verified, §10), so `k_score >= 2` is the minimum that can move information end to end; the grid spans well past that in both directions (`0` = no communication at all, `6` = three times the diameter) so the validation choice is informative rather than forced. |
| `K_trigger` | `ConsensusParams.k_trigger` | 4 | rounds | Max-consensus rounds for propagating a decision trigger. Same diameter argument. |
| `K_confirm` | `ConsensusParams.k_confirm` | 4 | rounds | Min/max-consensus rounds for confirming a mode before commit. Same diameter argument. |
| `H_commit` | `ConsensusParams.h_commit` | 10 | control steps (= 1.5 s) | **Must match** `recovery_v2.rollout(h_commit=10)`. The Recovery Event V2 labels that supervise the selector are generated by committing to a candidate mode for exactly 10 steps before handing over to the common continuation policy. If the runtime commit horizon differed from the labelling commit horizon, the selector would be trained on a decision it never actually gets to make. |
| `decision_interval` | `ConsensusParams.decision_interval` | 25 | control steps (= 3.75 s) | Forced decision-epoch cadence: an epoch is opened at least this often even with no trigger. `25 > H_commit = 10`, so each commit horizon completes and is observed before the next forced epoch can override it. |
| `confirm_margin` | `ConsensusParams.confirm_margin` | 0.0 | score units | Minimum `|z_keep - z_line|` required to accept a commit. Nominally 0 (no dead-band); non-zero values are a hysteresis knob, not a default. |

Link-model parameters (`symmetric=True`, `packet_loss=0.0`, `delay_steps=0`,
`async_offset_steps=0`) are nominal values only; the stress test overrides them
(§5).

### 4.1 The `R_comm = 3.0 m` justification, reproduced from the source

Transcribed from the `CommParams.r_comm` docstring:

> An `N=6` line at nominal spacing spans `5 x 0.9 = 4.5 m` end to end, so
> `R_comm = 3.0 m` leaves the line connected but *genuinely multi-hop* — the two
> end robots (4.5 m apart) cannot hear each other and must be reached through
> intermediate robots. Consensus is therefore not a disguised one-hop broadcast
> in the mode that matters most. An `N=6` keep grid (3 x 2, spacing 0.9) has
> maximum pairwise distance `~2.01 m < 3.0 m`, so keep is one-hop complete. The
> contrast between the two regimes is deliberate and is measured, not assumed.

**Independent verification of the `~2.01 m` figure.** Computed from
`RoleAssignment.from_index(6, 0.9).keep`, the keep template for `N=6` is a
2-row x 3-column grid (`cols = max(2, ceil(sqrt(6))) = 3`, `rows = ceil(6/3) = 2`)
with template-frame coordinates `{-0.45, +0.45} x {-0.9, 0.0, +0.9}`. Its maximum
pairwise distance is the grid diagonal:

```
sqrt(0.9^2 + 1.8^2) = sqrt(4.05) = 2.012461 m
```

The value computed by running the code is **2.012461 m** (float32 template
coordinates, distances in float64). This **agrees** with the docstring's
`~2.01 m`; no discrepancy to flag. The `N=6` line span computes to exactly
`4.500000 m`, also matching. Full output in §10.

---

## 5. Link assumptions

Stated once, from `system_model.LINK_ASSUMPTIONS`, so documents and tests agree.

| Property | Nominal | Statement (source: `LINK_ASSUMPTIONS`) |
|---|---|---|
| **symmetric** | Yes | `(i,j) in E_c` iff `(j,i) in E_c`. Justified because a single radio range gates both directions, and the Metropolis–Hastings weight rule needs symmetry for the consensus average to be preserved. The stress test breaks symmetry only through independent per-direction packet loss, which is handled as message loss, not as a directed graph. |
| **directed** | Not assumed | Asymmetric loss is modelled per-direction, so the *delivered* message graph can be transiently directed even though the link graph is symmetric. |
| **time-varying** | Yes | `E_c^t` is recomputed every communication period from current positions; robots enter and leave `R_comm` as the formation deforms. |
| **lossy** | Nominally lossless | The stress test sweeps 0 / 10 / 30 / 50 % independent per-message Bernoulli loss. |
| **delayed** | Nominally zero delay | The stress test sweeps 0 / 1 / 2 / 5 control steps of delivery latency. Delayed messages are accepted only while their age is `<= Delta_stale`. |
| **connectivity** | **NOT assumed globally** | Agreement claims are made only per connected component of `G_c`. Swarm-wide agreement is claimed only when `G_c` is connected, and that condition is measured per episode, never assumed. |

Note the interaction between *delayed* and `Delta_stale = 3`: a 5-step delivery
latency exceeds the staleness bound, so under that stress setting messages arrive
already expired and the neighbour is dropped from `N_i`. That is the intended
behaviour, not a bug — it is the regime in which the neighbour set genuinely
thins out.

---

## 6. Information available on each robot (exhaustive)

From `system_model.PERMITTED_LOCAL_SOURCES` — 10 entries, all listed.

| Source key | Meaning | Where it lands |
|---|---|---|
| `self_state` | own position, velocity | `RobotView.position`, `.velocity` |
| `self_id_and_role` | persistent ID, offline-configured formation role | `.robot_id`, `.role_keep`, `.role_line` |
| `local_obstacles` | obstacles observed within `R_obs` by own sensor | `.obstacles` |
| `one_hop_messages` | beacons / consensus messages from `N_i` | `.neighbours` (`NeighbourRecord` list) |
| `shared_goal` | mission goal / goal direction, same on all robots | `.goal`, `.mission_dir` |
| `shared_frame` | shared coordinate frame (explicit assumption) | implicit in every world-frame quantity; see §6.1 |
| `local_memory` | own history, epoch counter, committed mode | `.epoch_id`, `.steps_since_decision` |
| `committed_mode` | own current committed mode | `.committed_mode` |
| `model_parameters` | common offline-trained weights | loaded before `t = 0` |
| `controller_parameters` | common fixed-controller gains | loaded before `t = 0` |

Shared mission constants that are permitted to be read from the observation
dict, from `SHARED_MISSION_CONSTANTS` — 4 entries, all listed:

| Obs key | Why it is permitted |
|---|---|
| `goal` | identical on every robot, loaded before the mission rather than reconstructed at runtime |
| `corridor_dx` | shared mission-frame direction, same on every robot |
| `corridor_dy` | shared mission-frame direction, same on every robot |
| `scenario` | mission-configuration constant |

### 6.1 The two explicit assumptions hidden in this table

1. **Shared coordinate frame.** `shared_frame` is an assumption, not a
   derivation. Without it, `rotation(psi_mission)` would differ per robot and the
   role templates would not agree (`ROLE_LIMITATIONS["shared_frame"]`).
2. **Shared mission direction.** `mission_dir` is loaded, not negotiated. Every
   robot computes the same `R(psi_mission)` with no communication and no global
   state (`roles.rotation` docstring).

Both must be stated in any claim made from this system model.

---

## 7. Information PROHIBITED on each robot (exhaustive)

### 7.1 Prohibited global sources — `PROHIBITED_GLOBAL_SOURCES`, 17 entries

Any deployable tensor, feature or callable touching one of these is a violation.
This list is intended to be enforced executably by `guards.py`, not to be
documentation only.

| Prohibited source | Why it is global |
|---|---|
| `joint_state` | requires knowing every robot's state |
| `full_swarm_graph` | requires the whole adjacency structure, not the ego neighbourhood |
| `out_of_range_robot_state` | any robot beyond `R_comm` that is nonetheless read |
| `swarm_centroid` | mean over all robots |
| `global_formation_error` | derived from the swarm centroid |
| `global_min_distance` | min over all pairs |
| `global_min_ttc` | min time-to-collision over all pairs |
| `global_obstacle_centroid` | mean over all obstacles, including unsensed ones |
| `global_map` | map beyond own sensor footprint |
| `global_graph_pooling` | pooling over all nodes is an all-reduce in disguise |
| `global_all_reduce` | unbounded-round / all-to-all reduction |
| `centralized_mode_decision` | a single entity deciding the mode for everyone |
| `leader_selected_mode` | a distinguished robot deciding for everyone — breaks leaderlessness |
| `central_assignment_service` | runtime role/slot assignment from the joint state (the defect `roles.py` replaces) |
| `joint_action_function` | one function mapping joint state to all actions |
| `oracle_rollout_outcome` | requires simulating the future |
| `future_trajectory` | requires knowing the future |

### 7.2 Prohibited observation keys — `PROHIBITED_OBS_KEYS`, 11 entries

Concrete keys of the simulator's global `obs` dict that must never reach a
deployable feature builder. Checked by name in `guards.py` and by the ego-graph
feature audit.

| Obs key | Reason (from source comments) |
|---|---|
| `positions` | joint state |
| `velocities` | joint state |
| `formation_error` | derived from the swarm centroid |
| `obstacles` | full obstacle array, unbounded by sensor range |
| `obstacle_velocities` | full obstacle array, unbounded by sensor range |
| `subteam_ids` | split-mode remnant |
| `bottleneck` | computed from the joint state |
| `progress` | computed from the swarm centroid |
| `topology_switches` | episode-level global bookkeeping |
| `formation_scale_motion` | global formation statistic |
| `stall_counter` | global episode bookkeeping |

**Naming-collision warning.** `obs["progress"]` is prohibited (centroid-derived)
while `RobotView.local_progress` is permitted. They are different quantities:
`local_progress` must be computed from robot `i`'s own position and the shared
mission direction only. Any implementation that populates `local_progress` from
`obs["progress"]` satisfies the *name* check and violates the *contract*. This
is the single most likely place for a silent violation and should get a
dedicated test.

### 7.3 Prohibited structurally, not by key name

Independent of the key lists, no deployable function may accept:

- the `obs` dict itself,
- a positions array,
- an `(N, 2)` array of all robots,
- an index into "all robots".

Deployable functions take **only** a `RobotView` plus constant parameters.

---

## 8. Training-only information — `TRAINING_ONLY_SOURCES`, 4 entries

Available during training and offline analysis; never at runtime, never in a
deployable path.

| Source | Use | Why it cannot be runtime |
|---|---|---|
| `recovery_event_v2_label` | supervision target `y_tau` for the selector | a team-level label produced by counterfactual rollouts of the full simulator (`recovery_v2.rollout`), which requires the joint state and the ability to fork the world |
| `oracle_mode` | reference mode for analysis | derived from the same counterfactual rollouts |
| `global_episode_metrics` | offline evaluation and reporting | computed over the whole episode after it ends, from the joint state |
| `centralized_diagnostic_selector` | explicitly-labelled centralized reference for comparison | is by definition a central entity; used as a *baseline to compare against*, never as a component |

---

## 9. Runtime information

The complete set of quantities a deployable function may read at step `t`:

| Runtime input | Carrier | Bound |
|---|---|---|
| own state | `RobotView.position`, `.velocity` | 1 robot |
| own identity and roles | `.robot_id`, `.role_keep`, `.role_line` | constants from mission configuration |
| own decision memory | `.committed_mode`, `.epoch_id`, `.steps_since_decision`, `.local_progress` | own history only |
| shared mission constants | `.goal`, `.mission_dir` | identical on all robots, loaded before `t = 0` |
| self-sensed obstacles | `.obstacles` | within `R_obs = 3.0 m` |
| one-hop neighbour table | `.neighbours` | `j in N_i^t`: within `R_comm = 3.0 m` **and** `age <= 3` steps |
| offline parameters | model weights, controller gains | identical on all robots, loaded before `t = 0` |

Everything else is either prohibited (§7) or training-only (§8).

**Open item in the schema.** `RobotView.obstacles` is typed
`Sequence[Tuple[float, float, float]]`, but `system_model.py` does not state the
tuple layout. Consistency with the ego-relative rule of §2.1 requires it to be
`(relative x, relative y, radius)`; an absolute-coordinate layout would smuggle
world positions of obstacles into a deployable structure. The layout must be
fixed and documented when the simulation boundary (`comms.py`) is written, and
asserted by a test. It is *not* fixed by the contract as of this writing.

---

## 10. Template geometry and communication-graph properties (computed)

Computed with `RoleAssignment.from_index(N, 0.9)` and `CommParams().r_comm = 3.0`.
Distances are rotation invariant, so template-frame distances equal world-frame
distances for a formation exactly on template. "Diameter" is the hop diameter of
the disk graph `|| p_i - p_j || <= R_comm`. "One-hop complete" means the graph is
the complete graph, i.e. max pairwise distance `<= R_comm`.

| N | Template | Max pairwise distance (m) | Min pairwise distance (m) | Diameter at `R_comm = 3.0` | One-hop complete |
|---|---|---|---|---|---|
| 4 | keep (2x2 grid) | 1.272792 | 0.900000 | 1 | yes |
| 4 | line | 2.700000 | 0.900000 | 1 | yes |
| 6 | keep (2x3 grid) | 2.012461 | 0.900000 | 1 | yes |
| 6 | line | 4.500000 | 0.900000 | **2** | **no** |

Reading of this table:

- **`N=6` line is the only genuinely multi-hop configuration in the grid.** Its
  end robots are 4.5 m apart, beyond `R_comm = 3.0 m`, so end-to-end information
  transfer needs 2 hops. This is the configuration in which a consensus claim is
  not trivially a one-hop broadcast, and it is therefore the configuration that
  carries the evidential weight.
- **All three other configurations are one-hop complete on template.** Agreement
  results from `N=4` (either mode) and from `N=6` keep must be reported as
  one-hop-complete cases and must not be presented as evidence of multi-hop
  consensus.
- These are **on-template** figures. During an episode the formation deforms, so
  the realised graph can be sparser (a deformed keep can lose edges) or denser (a
  compressed line can gain them). The realised per-step diameter and connectivity
  must be *measured* per episode, not inferred from this table.
- `k_score = 4 >= 2 = ` the worst-case on-template diameter, with margin for
  transient deformation.

### 10.1 Reproduction

Script (throwaway, not part of the package):
`/private/tmp/claude-501/-Users-udy-rvt/11a6e7dd-155e-4e21-8fa2-4f8f305b038c/scratchpad/template_graph.py`

Verbatim output:

```
spacing = 0.90 m, r_comm = 3.00 m
N    mode  max_pair  min_pair  diameter  one_hop_complete
4    keep  1.272792  0.900000  1         True
4    line  2.700000  0.900000  1         True
6    keep  2.012461  0.900000  1         True
6    line  4.500000  0.900000  2         False

N=6 keep template coords (template frame):
[[-0.44999999 -0.89999998]
 [-0.44999999  0.        ]
 [-0.44999999  0.89999998]
 [ 0.44999999 -0.89999998]
 [ 0.44999999  0.        ]
 [ 0.44999999  0.89999998]]
N=6 keep max pairwise distance = 2.012461 m  (docstring claims ~2.01)
N=6 line span (end to end)     = 4.500000 m  (docstring claims 5 x 0.9 = 4.5)
N=6 line: end robots within r_comm? False
N=6 keep grid shape: cols=3 rows=2
```

---

## 11. What global state is still used, and where

Global state has not been deleted from the repository — it is required, in four
places, none of which is a deployable path.

| # | Use | Where | Why it is legitimate | Why it is not deployable |
|---|---|---|---|---|
| 1 | **Simulation** | `rvt_swarm/environment.py` and the single `simulate_*` boundary function | the simulator must integrate the joint dynamics; something has to know where everyone is | the boundary function is the simulated radio + sensor. It reads the global `obs` dict and emits per-robot `RobotView`s. It is explicitly **not deployable code**, carries a `simulate_` name prefix and a docstring saying so, and is the **only** function in the codebase permitted to read the global obs dict |
| 2 | **Recovery Event V2 label generation** | `rvt_swarm/recovery_v2.py` (`rollout`, `_clone`) | labels are counterfactual: fork the world, commit to a candidate mode for `H_commit = 10` steps, run the common continuation policy, score the outcome. This requires the joint state and the ability to clone the environment | it runs offline, before training, and produces `recovery_event_v2_label` — a `TRAINING_ONLY_SOURCES` entry. No runtime code path calls it |
| 3 | **Offline metric computation** | episode/aggregate metric modules | reporting formation error, minimum inter-robot distance, collision counts, task completion requires the joint state by definition — these are properties of the team, not of a robot | computed after the episode has ended, from logs. `global_episode_metrics` is a `TRAINING_ONLY_SOURCES` entry |
| 4 | **Centralized diagnostic reference** | explicitly-labelled centralized selector / baselines | an upper reference: what would a selector with full state have chosen? Needed to quantify the cost of decentralization | it is a *comparison baseline*, labelled centralized in every table. `centralized_diagnostic_selector` and `centralized_mode_decision` are respectively training-only and prohibited. It is never a component of the decentralized system |

**None of these four is in a deployable path.** The test of "deployable" is
mechanical: a deployable function accepts a `RobotView` plus constant
parameters, and nothing else. Uses 1–4 all take the `obs` dict, the environment,
or an episode log — so none of them can be mistaken for deployable code by that
test.

---

## 12. The exact claim that will be permissible

When the evidence in §13 exists, and **only** then, the permissible claim is,
verbatim:

> **Leaderless, fully decentralized execution using local observations and
> finite-round peer-to-peer communication under an explicitly stated
> communication-connectivity assumption.**

Unpacking each clause, and what each one costs:

| Clause | What must be true | What it does *not* say |
|---|---|---|
| *leaderless* | no distinguished robot, no election, no bidding, no assignment service; every robot runs the identical algorithm | it does not say the outcome is order-independent — that must be measured |
| *fully decentralized execution* | every deployable function takes only a `RobotView` plus constants; guards enforce it executably | it does not cover training, labelling, or metrics, which are centralized and offline by design (§11) |
| *local observations* | own state, own sensors within `R_obs`, one-hop messages from `N_i^t` | it does not include the sensing graph, which is declared but unused |
| *finite-round peer-to-peer communication* | `K_score`, `K_trigger`, `K_confirm` rounds per epoch, all finite and fixed; no all-reduce, no unbounded gossip | it does not claim asymptotic consensus |
| *under an explicitly stated communication-connectivity assumption* | connectivity of `G_c` is an assumption that is **measured per episode**, never assumed | it does not claim connectivity holds |

**The negative claim, stated as strongly as the positive one:**

> **Swarm-wide agreement will NOT be claimed when `G_c` is disconnected.**

Per `LINK_ASSUMPTIONS["connectivity"]`: agreement claims are made only per
connected component of `G_c`. Swarm-wide agreement is claimed only when `G_c` is
connected, and that condition is measured per episode, never assumed. Episodes
in which `G_c` was disconnected during the decision epoch must be reported
separately, with their component structure, and must not be pooled into a
swarm-wide agreement rate.

Two further claims that this system model does **not** license, recorded here so
they are not made by accident:

- **No attrition resilience.** If a robot drops out its template slot stays
  empty and the formation retains a gap (`ROLE_LIMITATIONS["dropout"]`).
- **No runtime role adaptation.** Roles are fixed for the whole mission; there is
  no reassignment mechanism (`ROLE_LIMITATIONS["no_reassignment"]`).

---

## 13. What is NOT yet proven (as of this document)

This document is a **specification**, not a result. At the time of writing, the
`rvt_swarm/decentralized/` package contains exactly three modules —
`__init__.py`, `system_model.py`, `roles.py` — and there are no tests for it in
`tests/`. Everything below is pending.

**Not yet written:**

- the `simulate_*` boundary function and `comms.py` (neighbour table construction)
- `guards.py` — the executable enforcement of §7. Referenced by
  `system_model.py` as the mechanism that makes the prohibited lists more than
  documentation; until it exists, the prohibited lists are documentation only
- the ego-graph feature builder, the consensus protocol, and the mode-conditioned
  local controller
- `test_pairwise_formation_geometry.py`, referenced in the `RoleAssignment`
  docstring as the test asserting roles are never recomputed at runtime

**Not yet measured — no number in the following list exists:**

- **Locality.** No test yet demonstrates that every deployable function is a
  function of `RobotView` alone. The claim "fully decentralized" rests entirely
  on this and it is currently unsupported.
- **Agreement rate.** The fraction of decision epochs ending in unanimous mode
  agreement, per connected component, is unmeasured — nominal, and under the
  loss/delay stress sweeps.
- **Realised connectivity.** The per-episode fraction of steps in which `G_c` is
  connected, and the realised graph diameter under deformation, are unmeasured.
  §10 gives on-template figures only.
- **`k_score` selection.** No point on `K_SCORE_GRID = (0, 1, 2, 3, 4, 6)` has
  been evaluated. The default `k_score = 4` in `ConsensusParams` is a
  placeholder, not a validated choice, and must be selected on validation
  layouts before any result is reported.
- **Decision gates.** No pass/fail gate for the decentralized selector has been
  run. No comparison against the centralized diagnostic reference exists.
- **Task performance.** Whether decentralized mode selection matches, degrades,
  or improves on the centralized selector is entirely unknown.

Until each of these produces a real measured number, the claim in §12 must not
be made. This document establishes what would have to be true; it does not
assert that any of it is.

---

## Appendix A — Provenance

| Fact in this document | Source |
|---|---|
| all parameter values | `rvt_swarm/decentralized/system_model.py` (`CommParams`, `ConsensusParams`, `K_SCORE_GRID`) |
| permitted / prohibited / training-only lists | the five frozensets in `system_model.py`, reproduced exhaustively (10 / 17 / 11 / 4 / 4 entries) |
| link assumptions | `system_model.LINK_ASSUMPTIONS`, all six keys |
| robot state components | field list of `system_model.RobotView` (13 fields) and `NeighbourRecord` (11 fields) |
| formation geometry, role limitations | `rvt_swarm/decentralized/roles.py` (`RoleAssignment`, `pairwise_offset`, `rotation`, `ROLE_LIMITATIONS`) |
| environment constants | `rvt_swarm/config.py` `EnvConfig` (`dt=0.15`, `nominal_spacing=0.9`, `sensing_radius=4.0`, `lidar_range=3.0`, `max_speed=0.9`) |
| `H_commit` cross-reference | `rvt_swarm/recovery_v2.py:85` (`h_commit: int = 10`) |
| §10 table and §4.1 verification | computed by running the script in §10.1 |

A machine-readable form of the contract is available from
`system_model.describe_contract()`; that function is the intended way to keep any
downstream document or test in sync with the code.
