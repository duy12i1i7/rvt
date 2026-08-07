# Phase 8E Executable Scenario Geometry

## Authority and frames

This additive contract completes `rvt-scenario-layout/v1` without modifying any
Phase 8 layout. The machine authority is
`results/rvt_fd24/executable_scientific_protocol_v1.json`, schema
`rvt-executable-scientific-protocol/v1`.

The world frame is explicitly right-handed with origin `(0,0)`, x axis `(1,0)`,
y axis `(0,1)`, and bounds `x in [-18,18] m`, `y in [-6,6] m`. These bounds contain
the N=24 LINE half-length at the frozen start and goal, every declared family
range, and configured clearances. They are protocol values, not simulator
defaults.

For start `s` and goal `g`, the mission origin and initial topology origin are
exactly `s`. The longitudinal axis is `e=(g-s)/||g-s||`, the lateral axis is
`n=(-e_y,e_x)`, and heading is `atan2(e_y,e_x)`. A zero or nonfinite goal vector
is invalid. No legacy `start_center`, hidden origin, fixed heading, headroom
category, trajectory outcome, or label participates.

## ScenarioLayout mapping

| Field | Units | Meaning | Exact runtime formula | Valid range | Dependency | Simulator use | Robot-visible representation | Invalidity |
|---|---|---|---|---|---|---|---|---|
| `schema_version` | ID | layout schema | require `rvt-scenario-layout/v1` | exact ID | none | validation | none | mismatch |
| `generator_version` | ID | generator identity | require `rvt-compact-line-geometry/v1` | exact ID | none | validation | none | mismatch |
| `layout_id` | ID | layout identity | copy unchanged | nonempty | split record | audit | none | missing/duplicate |
| `family_id` | ID | compiler selector | exact F1-F10 dispatch | F1-F10 | family contract | compiler | never a control input | unknown/mismatch |
| `split` | ID | access namespace | train/validation only | train, validation | split manifest | access guard | none | final/unknown |
| `variant_index` | count | canonical variant | identity only | nonnegative | split record | audit | none | invalid identity |
| `generation_seed_commitment` | SHA-256 | layout provenance | copy unchanged | valid commitment | seed contract | audit | none | missing |
| `start_center_meters` | m | mission/topology origin | `s` | finite, in bounds | none | initialization | shared static origin | invalid frame |
| `goal_center_meters` | m | goal-region center | `g` | finite, in bounds, `g!=s` | runtime tolerance | evaluator | shared goal | invalid frame |
| `corridor_centerline_meters` | m | route/passage reference | canonical piecewise-linear polyline | finite, strictly increasing world x | family compiler | analytic geometry | never complete map | nonmonotone/self-invalid |
| `nominal_passage_width_meters` | m | inner free width | passage tube width | positive | primitive width | collision world | local boundary observations only | width mismatch |
| `static_obstacles` | m | occupied geometry | compile by primitive rules below | finite, positive dimensions | world bounds | collision/sensor truth | ego-relative support discs | unknown/out of bounds |
| `dynamic_obstacle_paths` | m,s | moving circles | F9 timestamped contract | positive radius, increasing time | F9 contract | dynamic world | current local circle only | malformed/non-F9 use |
| `bypass_available` | bool | explicit bypass | true only for F6 | exact family relation | F6 parameters | validity/audit | no label | inconsistent declaration |
| `communication_profile` | ID | channel process | nominal/F8 dispatch | declared IDs | F8 contract | channel | delivered messages only | unknown profile |
| `initial_topology_id` | topology ID | initial role template | require COMPACT (5) | COMPACT in v1 | topology registry | initialization | local role metadata | KEEP/undeclared LINE |
| `episode_horizon_seconds` | s | absolute timeout | first control boundary at or after horizon | finite, positive | control period | termination | local clock may know horizon | invalid horizon |
| `canonical_parameters` | named SI | family parameters | parse once and cross-check primitive data | finite, unique names | family compiler | geometry/process | only values explicitly shared | duplicate/conflict |
| `diagnostic_headroom_by_team_size` | category | diagnostic expectation | audit-only, never consumed by compiler | frozen category | none | no execution use | prohibited | any execution dependency |

## Primitive semantics

Circles and `central_blocker` are closed disks with stored center and radius.
Contact is collision. A straight corridor `(x0,x1,w)` is active over world-x
slab `[x0,x1]`; inside that slab, free space is the closed Euclidean tube of
half-width `w/2` around the clipped layout centerline. The remaining in-bounds
space in the slab is occupied wall material.

`polyline_corridor(w,entry)` starts at the first interior control-point x and
ends at its reflection across world x=0. `s_corridor(w,amplitude)` starts at the
first interior point and ends at the last. Both use the exact stored polyline,
closed round distance-to-segment joins, and passage length equal to the sum of
clipped segment lengths. A spline was rejected because no tension, tangent, or
endpoint-derivative parameter was frozen.

| Family | Executable geometry |
|---|---|
| F1 | two explicit circles; no confining passage |
| F2 | one analytic straight corridor |
| F3 | one offset polyline corridor |
| F4 | one sampled S polyline corridor |
| F5 | two ordered analytic straight corridors; stored separation unchanged |
| F6 | explicit central disk and polyline bypass with circular fillets of stored radius |
| F7 | three explicit clutter circles |
| F8 | one straight corridor plus the F8 channel process |
| F9 | no static passage and one dynamic circle |
| F10 | one straight corridor below declared clearance |

F6 uses the stored control points, stored fillet radius and stored clearance.
Fillet tangent points must remain on adjacent segments and the route must clear
the inflated blocker. No family is assigned an inferred obstacle or route from
diagnostic success.

## Clearance and sensing

Circle collision uses center threshold
`robot_radius + max(safety.obstacle_clearance_margin, circle_radius)`, exactly
matching the frozen local safety semantics. Analytic wall collision uses surface
distance `robot_radius + 0.02 m`; `0.02 m` is the declared surface margin already
represented by the frozen `0.37 m = 0.35 m + 0.02 m` obstacle margin.

Circles are observed as true relative centers and radii when their center is
within `R_obs`. Analytic inner boundaries are converted deterministically into
virtual support disks: radius `0.35 m`, maximum arc spacing `0.175 m`, endpoint
inclusion, canonical primitive/side/arc ordering, and centers inset `0.35 m`
into occupied space. Robots receive only current ego-relative disks within
`R_obs`. Analytic occupied sets, world bounds, future boundary samples and the
complete layout remain simulator-only. Support disks are sensor tokens; analytic
geometry remains collision truth.

## Compilation and invalidity

The compiler reads only canonical train/validation split records. Canonical JSON
and SHA-256 make each output independent of enumeration order. The compiler
rejects unknown/missing fields, nonfinite data, nonpositive dimensions,
nonmonotone centerlines/times, family/primitive conflicts, width disagreement,
unsupported topology, bounds failures and initial collisions.

Nominal initial invalidity is retained per team size rather than repaired by
moving the origin. Perturbed initial invalidity is retained as one rejected job
slot with no resampling. This is an executable exclusion rule, not Category D.

Rejected alternatives were legacy obstacle-center wall grids, undocumented wall
thickness, Catmull-Rom interpolation, successful-trajectory inferred exits, and
headroom-selected geometry. Each would add an unfrozen parameter or outcome
dependency.
