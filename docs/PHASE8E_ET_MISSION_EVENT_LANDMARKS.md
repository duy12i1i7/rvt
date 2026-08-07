# Phase 8E-PC-ET — Mission Event Landmarks (ET-3)

Deterministic mission-space landmarks, taken **only** from geometry already
present in the approved execution specification. No obstacle is added, no
passage is moved, and no landmark is derived from a target label, a headroom
category, a candidate outcome or a trajectory result.

## Frame

Landmarks are expressed in the mission frame of each layout: origin at
`start_center_meters`, longitudinal axis `e = (g-s)/||g-s||`, lateral axis
`n = (-e_y, e_x)`. This is the same frame the compiled `mission_frame` block
already defines, so no new frame convention is introduced.

## Landmark kinds

| kind | source field | lateral extent used for observability |
|---|---|---|
| `passage_entry` | `passages[i].entry_position_meters` | `half_width + support_disc_radius` (0.35 m) |
| `passage_exit` | `passages[i].exit_position_meters` | same |
| `circle` | `static_obstacles[i].center_meters` | the circle centre itself |
| `dynamic_circle` | midpoint of `dynamic_obstacles[i].waypoints` endpoints | the mission axis, since the path sweeps across it |

The support-disc radius and the sensing range are the frozen values already in
`static_obstacle_contract.sensor_conversion` and `sensing`
(`support_disc_radius_meters = 0.35`, `obstacle_sensing_range_meters = 3.0`).

## Observability rule

A landmark first becomes locally observable when it enters `R_obs` of **some
robot of the nominal role template**, not of a point mass at the origin:

    s_trigger = min over template roles i of
                ( L_landmark - r_i,longitudinal - sqrt(R_obs^2 - (lat_landmark - r_i,lateral)^2) )

with the role excluded when `|lat_landmark - r_i,lateral| >= R_obs`. If every
role is excluded, the landmark is never observable and the family legitimately
declares `NO_EVENT`.

The template-aware form is load-bearing, not decoration. F7's clutter circles
sit at |lateral| = 2.73–3.12 m against `R_obs = 3.0 m`; a point-mass test calls
several of them unobservable, while a laterally offset COMPACT role sees them.
The distinction changes F7's classification.

## Which landmarks may originate which evidence

| family | narrowing evidence (COMPACT -> LINE) | opening evidence (LINE -> COMPACT) | no-event condition |
|---|---|---|---|
| F1 | none — both circles lie beyond `R_obs` laterally | none | **declared NO_EVENT**; open field with no observable constriction |
| F2 | `passage_entry-0` | `passage_exit-0` | — |
| F3 | `passage_entry-0` (offset polyline) | `passage_exit-0` | — |
| F4 | `passage_entry-0` (S polyline) | `passage_exit-0` | — |
| F5 | `passage_entry-0`, then `passage_entry-1` | `passage_exit-0`, then `passage_exit-1` | — |
| F6 | `circle-0` (central blocker) | — (single declared event) | — |
| F7 | `circle-0` (first clutter circle) | past `circle-0` | — |
| F8 | `passage_entry-0` | `passage_exit-0` | — |
| F9 | `dynamic-0` band | past `dynamic-0` | — |
| F10 | `passage_entry-0` | — (sub-clearance passage; no exit event declared) | — |

## Sequence preservation

Each family's declared event *count*, *order* and *target topology* are taken
unchanged from the superseded table; only the trigger is re-derived. Where a
later landmark becomes observable before an earlier one — which happens in F5,
whose second bottleneck entry is visible at 2.66 m while the first exit is at
3.50 m — the later trigger is clamped to its predecessor so the declared
sequence cannot be reordered.

## Opening semantics

An opening landmark marks the point at which the forward observation sector
clears past the corresponding feature. It does **not** by itself request
COMPACT: the already frozen opening and hysteresis semantics of S3
(`REQUEST_COMPACT` requires complete open observation, or width at least the
COMPACT requirement plus twice the spacing margin) still govern whether the
request is issued, and the frozen `commitment_seconds` still gates re-request.
