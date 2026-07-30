# Decentralized Formation-Role Protocol

Specification of the persistent formation-role mechanism in
`rvt_swarm/decentralized/roles.py`, the pairwise geometry it defines, and the
assumptions and limitations that come with it.

Evidence: `tests/test_pairwise_formation_geometry.py` (63 tests).
Run with:

```
cd /Users/udy/rvt && PYTHONPATH=. .venv/bin/python -m pytest tests/test_pairwise_formation_geometry.py -q
```

Constants referenced below come from `system_model.py` (`KEEP = 0`, `LINE = 2`,
`r_comm = 3.0 m`, `delta_stale_steps = 3`) and `EnvConfig`
(`nominal_spacing = 0.9 m`). Mode `SPLIT` is removed; only keep and line exist.

---

## 1. What a role is

Each robot carries a persistent integer ID and two **role coordinates**, one per
mode, expressed in a template frame:

```
r_i^keep in R^2 ,  r_i^line in R^2
```

Both are **mission constants**. They are computed once, before `t = 0`, and
burned into the robot alongside its ID, exactly like the controller gains or the
goal. Nothing in the control loop recomputes them. They are stored in a frozen
dataclass `RoleAssignment(keep, line, spacing, source)`; mutation raises.

The desired displacement from robot *i* to robot *j* in mode `tau` is

```
d_ij^tau  =  R(psi_mission) [ r_j^tau - r_i^tau ]
```

where `R(psi_mission)` is the rotation carrying the template `+x` axis onto the
shared mission direction. Robot *i* computes this from **three quantities only**:
its own role, the neighbour's role (received in the neighbour's beacon), and the
shared mission direction. No positions enter. `pairwise_offset(role_i, role_j,
mission_dir)` has exactly those three parameters and nothing else.

Two structural consequences, both of which are tested rather than asserted:

* **Exact antisymmetry.** `d_ij = -d_ji` bit-exactly, because the quantity is a
  rotation applied to a difference. Both robots of a pair therefore agree on the
  geometry with no negotiation, no tie-break, and no shared convention beyond
  the mission direction.
* **Translation invariance.** Adding a common vector to every role coordinate
  leaves every `d_ij` unchanged. The swarm centroid is therefore never needed,
  and cannot be inferred from the formation term.

---

## 2. The keep template

Grid, index-addressed. For `N` robots with spacing `s`:

```
cols = max(2, ceil(sqrt(N)))
rows = ceil(N / cols)
(row_i, col_i) = divmod(i, cols)

r_i^keep = ( (row_i - (rows-1)/2) * s ,  -(col_i - (cols-1)/2) * s )
             \_____ along mission _____/   \______ lateral ______/
```

`N = 4` gives a 2x2 block; `N = 6` gives a 3-wide, 2-deep grid (`cols = 3`,
`rows = 2`).

The lateral coordinate carries an explicit minus sign. This is not cosmetic.
The centralized template builds its lateral axis as
`lateral = (corridor_y, -corridor_x)` — the mission direction rotated **-90°** —
whereas a proper rotation `R(psi)` maps the template `+y` axis to **+90°**.
Negating the template lateral coordinate makes the two conventions agree while
keeping `R` a proper rotation (`det = +1`), which the equivariance argument
needs. Without the negation the decentralized keep formation would be the
centralized one *mirrored about the mission axis*: congruent as an unordered
point set, but assigning robots to mirrored slots.

`test_keep_template_reproduces_centralized_grid_pairwise` checks the pairwise
tables agree to `< 1e-6 m` for `N in {4, 6}` across eight mission directions
including non-axis-aligned ones.
`test_keep_pairwise_comparison_would_catch_a_mirrored_template` feeds the same
comparison a deliberately mirrored table and confirms it is rejected with a gap
of `2 (cols-1) s`, so the passing result above is evidence about the convention
and not an artefact of the grid being symmetric.

Comparison is on **pairwise differences** because the centralized template is
centroid-anchored (`target_positions = centroid + offsets`, `controllers.py:174`)
while the decentralized one is defined only up to a common translation. Pairwise
differences are precisely the quantity the decentralized controller consumes.

The centralized keep branch was *already* index-based (`divmod(i, cols)`), so it
required no runtime joint-state access and is reproduced directly. Only the line
branch had to be replaced.

---

## 3. The line template

Single file along the mission direction:

```
r_i^line = ( (rank_i - (N-1)/2) * s , 0 )
```

The lateral coordinate is exactly `0.0` for every robot, and consecutive ranks
are `s = 0.9 m` apart (exact up to float32 representation, ~1e-7). The file is
centred on the template origin, and the head-to-tail span is `(N-1) s`
(`2.7 m` at `N = 4`, `4.5 m` at `N = 6`).

`rank` is a permutation of `0 .. N-1` — each rank used exactly once — under both
constructors.

---

## 4. Role ordering: two constructors, both reported

### `RoleAssignment.from_index(n, spacing)` — source `"index"`

`rank_i = i`. Roles depend on nothing but the persistent robot ID. This is the
strictest possible reading of "offline persistent role": there is no input
channel through which any state could enter — the signature is literally
`(n, spacing)`.

### `RoleAssignment.from_initial_formation(initial_positions, mission_dir, spacing)` — source `"initial_formation"`

Ranks follow the robots' ordering along the mission direction in the **initial**
configuration, ties broken by robot ID so the result is deterministic:

```
order = argsort_stable( p_i(0) . mission_dir , then i )
rank_{order[k]} = k
```

Called **exactly once, before `t = 0`**, as part of configuring the mission —
the same status as loading the goal. After construction the roles are frozen
constants; no control step may call it.

### Why both exist — the honest cost of `from_index`

`from_index` is free at runtime but **may require robots to trade places**. If
the spawn order along the corridor disagrees with the ID order, forming the line
demands a crossing manoeuvre at `t = 0`: robot 3 may have to overtake robot 1.
In a cluttered corridor that is a real cost — extra path length, extra
robot-robot proximity events, and a transient the controller has to absorb
before the mission proper begins.

`from_initial_formation` removes that transient by assigning each robot the slot
it is already closest to in the corridor ordering, so no crossing is required at
`t = 0`. The price is that role assignment reads the initial positions — which
is legitimate as mission configuration, but is strictly more than "ID only".

Neither is silently preferred. **Both are reported as separate arms**, so the
cost of the strict variant is visible in the results rather than hidden by a
convenient default.

---

## 5. The formation graph

Formation terms come from exactly the robots in `N_i`: the one-hop communication
neighbours whose most recent message is valid.

* Membership is by radio, not by sensing: `(i,j) in E_c` iff the two are within
  `r_comm = 3.0 m`. `r_sense = 4.0 m` exists and is documented, but is not used
  to populate `N_i` — the stricter choice.
* A neighbour whose newest message is older than `delta_stale_steps = 3` steps
  (`0.45 s`) is marked invalid and excluded.
* The graph is **time-varying**: `E_c^t` is recomputed every communication
  period as the formation deforms.

The local formation residual is the sum over valid neighbours of
`(p_j - p_i) - d_ij`, divided by `|N_i| + 1`.

This matters for the two modes in opposite ways, deliberately:

* **keep**, `N = 6`: the 3x2 grid at nominal spacing has maximum pairwise
  distance ~`2.01 m < 3.0 m`, so the formation graph is **complete** — one hop
  reaches everyone.
* **line**, `N = 6`: the file spans `4.5 m` end to end, so the two end robots
  **cannot hear each other**. The formation graph is a path, and the protocol is
  genuinely multi-hop in exactly the mode where it matters most.

Global connectivity is **not assumed**. Agreement claims are made per connected
component, and connectivity is measured per episode.

---

## 6. Assumptions

### Common coordinate frame (required)

Every robot must express positions and the mission direction in a **common
frame**. `R(psi_mission)` is computed independently on each robot from the
shared mission direction; if the frames differed, each robot would build a
different `R`, the templates would not agree, and the pairwise constraints would
be mutually inconsistent. There is no frame-alignment protocol here. This is an
explicit assumption, not a proven property.

Common orientation is what is actually needed — a common *origin* is not, since
the geometry is translation-invariant (§1).

### Shared goal / shared mission direction (required)

`goal`, `corridor_dx`, `corridor_dy` and `scenario` are permitted shared mission
constants: identical on every robot and loaded before the mission rather than
reconstructed at runtime. The mission direction feeds `R(psi_mission)`; the goal
supplies the absolute placement that the formation term deliberately does not.

The centralized reference `controllers._desired_offsets` multiplies the raw
`(corridor_dx, corridor_dy)` into the template without normalising it, so the
centralized/decentralized cross-check is only well posed for a **unit** corridor
vector. The environment always supplies one (checked to `1e-3` by
`test_environment_supplies_a_unit_mission_direction`); `rotation()` normalises
internally regardless, and returns the identity for a degenerate zero direction
rather than producing NaNs.

### Rigidity

Pairwise displacement constraints determine the formation only **up to a common
translation**. That is sufficient here: absolute placement comes from the shared
goal term, not from the formation term. It is also the property that makes the
centroid unnecessary.

---

## 7. Missing neighbours, dropout, and what is *not* claimed

### Missing neighbour — graceful

A formation neighbour that is out of range, stale, or lost to packet loss simply
**contributes no formation term**. The remaining pairwise terms still define a
consistent geometry, because the constraints are pairwise rather than
centroid-referenced: there is no global quantity to corrupt. With *no* valid
neighbours the formation term is zero — the robot is not "in formation" with
anything, and the goal and avoidance terms carry it until a neighbour reappears.

This is the concrete benefit of the pairwise formulation. A centroid-anchored
term would need an estimate of the centroid, and a missing robot would bias that
estimate for everyone.

### Robot dropout — a real limitation

If a robot drops out, **its slot in the template stays empty**. Survivors keep
their own roles and the formation retains a gap. Nothing re-packs the template,
nothing shifts ranks down, nothing fills the hole.

In line mode the gap is also a connectivity hazard. `k` consecutive missing
ranks leave the surviving neighbours `(k+1) * 0.9 m` apart: `1.8 m` for one
dropout and `2.7 m` for two — both still inside `r_comm = 3.0 m` — but `3.6 m`
for three, at which point the file **partitions** into two components that can
no longer reach each other. A re-packing mechanism would avoid this; there is
none.

### No automatic role reassignment — explicit

There is **no election, no bidding, no auction, and no assignment service** at
runtime. A robot keeps its role for the whole mission. Roles are never
recomputed, never renegotiated, and never traded.

### No attrition-resilience claim is made

Stated plainly: **this protocol makes no claim of resilience to robot
attrition.** It is not evaluated under dropout, and the dropout behaviour above
is a limitation, not a feature. Any future attrition claim would require a
reassignment mechanism that does not exist in this codebase, plus its own
evaluation.

---

## 8. Contrast with the centralized mechanism this replaces

### What the centralized version did

`rvt_swarm/controllers.py`, line-mode branch of `_desired_offsets`:

```python
if mode == 2:
    order = np.argsort(pos @ corridor)          # controllers.py:79
    offsets = np.zeros((n, 2), dtype=np.float32)
    for rank, robot_idx in enumerate(order):
        offsets[robot_idx] = corridor * ((rank - (n - 1) / 2) * spacing)
    return offsets
```

`pos` here is `obs["positions"]`, the `(N,2)` **joint state**. The sort ranks all
`N` robots against each other, and `_desired_offsets` is called from
`expert_action` at **every control step** (`controllers.py:173`), on the
`obs` dict, alongside `centroid = pos.mean(axis=0)`.

### Why that is a central runtime assignment service

Three properties, each individually disqualifying:

1. **It reads the joint state.** `np.argsort(pos @ corridor)` needs the
   projections of *all* `N` robots simultaneously. No robot possesses that. It is
   `positions`, a prohibited observation key.
2. **It runs at runtime, every step.** Not a configuration step — a per-step
   computation inside the control loop.
3. **It is a single global decision point.** One sort produces one consistent
   ranking for the whole team. Robot *i*'s slot depends on where robots it has
   never heard from happen to be. Remove the central computer and no robot can
   reproduce the answer; run it independently on partial information and
   different robots get *different, mutually inconsistent* rankings — two robots
   can claim the same rank, and the assignments would no longer be antisymmetric.

Because the ranking is recomputed each step, the assignment can also **change
mid-episode** when two robots' projections cross, silently reassigning slots
during motion.

### How persistent roles remove it

| | centralized `_desired_offsets` (line) | persistent roles |
|---|---|---|
| input | `obs["positions"]`, all `N` robots | own ID / own role + neighbour's role |
| when | every control step | once, before `t = 0` |
| who computes | one central process | each robot, independently |
| result under partition | undefined (needs everyone) | unchanged — roles are constants |
| assignment stability | may flip when projections cross | fixed for the mission |
| what is communicated | nothing (shared memory) | 2 floats per mode, per beacon |

The sort is not decentralized — it is **deleted**. The ranking it produced is
moved from runtime to mission configuration, where reading the initial
configuration is as legitimate as reading the goal. What remains at runtime is a
subtraction of two role coordinates and one rotation, both of which robot *i*
can perform alone.

**The cost of that deletion** is §4: with `from_index`, robots may have to trade
places, because there is no longer anything that adapts the assignment to where
the robots actually are. The centralized sort bought a crossing-free assignment
by paying with the joint state, every step. `from_initial_formation` buys the
same thing by paying once, offline. Both arms are reported.

---

## 9. Evidence

`tests/test_pairwise_formation_geometry.py`:

| property | test |
|---|---|
| `d_ij = -d_ji` bit-exactly, both modes, `N in {4,6}`, 8 mission directions | `test_pairwise_offset_is_exactly_antisymmetric` |
| common translation of the template changes nothing | `test_pairwise_offsets_are_translation_invariant` |
| constructing twice gives identical tables | `test_constructing_roles_twice_gives_identical_tables` |
| roles unchanged after the swarm moves > 0.5 m in the real env | `test_roles_do_not_change_as_the_swarm_moves` |
| tables are immutable | `test_role_assignment_is_immutable` |
| only `from_initial_formation` has a position argument, anywhere in the module | `test_only_from_initial_formation_reads_positions` |
| `R` orthonormal, `det = +1`, maps `(1,0)` to the unit mission direction | `test_rotation_is_a_proper_rotation_mapping_x_onto_the_mission_direction` |
| zero mission direction gives identity, not NaN | `test_rotation_of_degenerate_direction_is_identity` |
| keep template equals the centralized grid, pairwise | `test_keep_template_reproduces_centralized_grid_pairwise` |
| that comparison would reject a mirrored template | `test_keep_pairwise_comparison_would_catch_a_mirrored_template` |
| line is single file, exact `0.9 m` rank spacing, zero lateral | `test_line_template_is_single_file_at_nominal_spacing` |
| both constructors give valid rank permutations | `test_both_constructors_give_valid_rank_permutations` |
| `from_initial_formation` orders along the mission direction, ties by ID | `test_from_initial_formation_orders_ranks_along_the_mission_direction` |
| offset computable from three local quantities alone | `test_offset_needs_only_own_role_neighbour_role_and_mission_direction` |
| no absolute neighbour position in the record | `test_neighbour_record_exposes_no_absolute_position` |
| deployable geometry takes no joint-state argument | `test_deployable_geometry_takes_no_joint_state_argument` |
| passing an `(N,2)` array to `pairwise_offset` raises | `test_pairwise_offset_rejects_a_positions_array` |
| `from_initial_formation` never called from a `step`/`control` function | `test_from_initial_formation_is_never_called_from_runtime_code` |
| that AST guard detects a planted violation | `test_the_ast_guard_detects_a_planted_runtime_violation` |
| no prohibited obs key read in `roles.py` | `test_roles_module_never_reads_prohibited_obs_keys` |
| `roles.py` contains no `simulate_` boundary function | `test_no_simulation_boundary_function_lives_in_roles` |
