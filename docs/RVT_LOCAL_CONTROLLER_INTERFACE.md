# RVT Robot-Local Controller Interface

Schema: `rvt-robot-local-controller/v1`.

The authoritative Phase 6 controller is constructed once from immutable
`RuntimeConfig` and evaluates one immutable `RobotLocalControllerInput` at a
time. It returns one immutable `RobotLocalControllerOutput`. Neither type can
contain a joint-state tensor or a joint action.

## Input contract

| Field | Semantics | Units/source |
|---|---|---|
| observer robot ID and role ID | persistent identity and mission-setup role | identifiers |
| timestamp | current local evaluation time | s |
| own position and velocity | observer state in shared mission frame | m, m/s |
| forced topology ID | externally fixed KEEP, COMPACT or LINE | canonical registry ID |
| shared goal origin | static target of the centered topology origin | m |
| mission direction | predeclared shared-frame heading | unit direction after normalization |
| local topology slice | own role offset and only nominal formation-neighbour offsets for the forced topology | registry-derived m |
| peer states | ego-relative states received through one-hop messages, with age and validity | m, m/s, s |
| obstacle observations | ego-relative circle primitives accepted by local sensing, with radius, velocity, age, confidence and validity | SI |
| runtime configuration hash | binds the input to the controller's immutable configuration | SHA-256 |
| validity | explicit producer status | Boolean |

The controller rejects unknown topology IDs, wrong observer/slice association,
nonfinite values, invalid dimensions and runtime-hash mismatch. Peers outside
the communication range cannot enter formation or safety calculations.
Obstacles outside `R_obs` cannot enter obstacle or safety calculations.

Freshness is evaluated from the immutable maximum message age. Fresh peers may
enter formation and safety. A stale record never enters formation; if retained
for safety diagnostics, its clearance is conservatively inflated by the
maximum motion possible during its age. Missing peers create no fabricated
formation measurement and are explicitly counted in diagnostics.

## Output contract

The output contains own `formation_term`, `goal_term`, `damping_term`,
`obstacle_term`, their unbounded sum `base_action`, the bounded
`projected_action`, projection intervention and infeasibility flags, active
local constraint descriptors, saturation state, validity and diagnostics.
Every action/term has shape `(2,)` and units m/s^2.

Diagnostics are write-only outputs. No diagnostic value is fed back into the
same controller evaluation or used to select topology. Diagnostic embeddings,
learned scores, Metric V3 values and scenario labels are not accepted inputs.

## Static topology geometry

At mission setup, `prepare_robot_local_topology_metadata` reduces registry
templates to one slice per robot. The forced adapter selects exactly one
candidate slice before calling the controller. Runtime control therefore sees
the observer's own role offset and locally relevant pairwise offsets, never a
complete topology template.
