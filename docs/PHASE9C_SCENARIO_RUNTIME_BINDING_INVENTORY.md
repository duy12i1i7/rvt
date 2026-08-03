# Phase 9C Scenario-to-Runtime Binding Inventory

## Scope and stop result

This inventory was performed on blocked Phase 9 commit
`84f48dfd9244793cd7559e5a0b917292168b384e`, before any runtime-binding
implementation. It inspected only repository source, frozen train/validation
descriptors, and already published audit artifacts. Final-test geometry and the
sealed Study A N=24 namespace were not opened.

RB-1 stops implementation because required executable values remain Category D.
The blocking values are static corridor geometry, F8 communication schedules,
F9 dynamic-obstacle dynamics, scientific initial-condition disturbances, four
source-policy definitions, and the complete task evaluator. A binding compiler
would have to choose new scientific semantics for each of these values.

Classification used below:

- **A**: directly stored in `ScenarioLayout`.
- **B**: uniquely derived from stored fields and an already frozen contract.
- **C**: simulator-internal state generated from an approved seed by an already
  specified generator.
- **D**: missing or scientifically ambiguous policy.

## Authoritative ScenarioLayout fields

The authoritative schema is the frozen dataclass in
`rvt_swarm/phase8/scenario.py`. The table includes all 18 fields in declaration
order. "Global" means simulator/audit scope; it does not authorize that value as
a robot-local control input.

| ScenarioLayout field | Scientific meaning | Runtime destination | Visibility | Units | Derivation/class | Required | Missing policy |
|---|---|---|---|---|---|---|---|
| `schema_version` | Layout record contract | Binding provenance | Global audit | identifier | Direct, A | Yes | None |
| `generator_version` | Geometry-generator identity | Binding provenance | Global audit | identifier | Direct, A | Yes | None |
| `layout_id` | Human-readable layout identity | Episode identity | Global audit | identifier | Direct, A | Yes | None |
| `family_id` | F1-F10 family membership | Episode/evaluator audit metadata | Global audit; prohibited as a control input | identifier | Direct, A | Yes | None |
| `split` | Train or validation membership | Split guard and episode identity | Global audit | identifier | Direct, A | Yes | None for nonfinal execution |
| `variant_index` | Canonical within-split variant | Episode identity | Global audit | count | Direct, A | Yes | None |
| `generation_seed_commitment` | Commitment to layout-generation seed | Provenance only | Global audit | SHA-256 commitment | Direct, A | Yes | The commitment is not an executable RNG state, and no such use is required |
| `start_center_meters` | Initial topology origin in the shared mission frame | Mission-frame origin and exact template placement | Shared static mission setup | m | Direct, A | Yes | None; it must not be renamed or defaulted as legacy `start_center` |
| `goal_center_meters` | Downstream goal center | Shared goal and offline evaluator | Shared goal; full evaluator remains global | m | Direct, A | Yes | Goal-region radius and terminal task rule are not stored; see D6 |
| `corridor_centerline_meters` | Canonical route/corridor centerline descriptor | Static-world compiler and audit geometry | Global simulator | m | Direct descriptor, A | Yes for F3/F4/F6 | Boundary construction and route-following semantics are missing; see D1 |
| `nominal_passage_width_meters` | Declared free passage width | Static-world compiler and geometry checks | Global simulator | m | Direct descriptor, A | Yes | It does not define wall thickness, exclusion geometry, or sampling; see D1 |
| `static_obstacles` | Versioned static primitive descriptors | Static world, collision model, local sensor source | Global world; robot receives only local observations | m by primitive | Direct descriptor, A | Yes | Circle-like primitives are explicit; corridor primitive compilation is D1 |
| `dynamic_obstacle_paths` | Radius and timestamped waypoints | Dynamic-world provider and local sensor source | Global world; robot receives only current local observations | m, s | Direct descriptor, A | Required for F9 | Interpolation and conflicting speed semantics are D2 |
| `bypass_available` | Declared existence of a feasible bypass | World validity/audit metadata | Global audit; not a control label | boolean | Direct, A | Yes | F6 branch boundaries and executable free-space region are incomplete under D1 |
| `communication_profile` | Named episode communication condition | Communication provider | Global channel; robot receives delivered messages only | identifier | Direct descriptor, A | Yes | Exact delay/loss/disconnection schedule is D3 |
| `initial_topology_id` | Primary initial committed topology | Role template and per-robot initial mode | Shared/local immutable topology metadata | topology ID | Direct, A | Yes | Every current family stores COMPACT; KEEP is not admitted |
| `episode_horizon_seconds` | Maximum source/counterfactual episode time | Simulator termination clock | Global simulator | s | Direct, A | Yes | None for the horizon itself |
| `canonical_parameters` | Canonical family parameter tuple | Provenance, duplicate guard, compiler cross-check | Global audit | named SI strings | Direct, A | Yes | F9 speed conflicts with its timestamped path; see D2 |
| `diagnostic_headroom_by_team_size` | Diagnostic preflight expectation | Audit only | Never robot-visible and never an outcome label | category | Direct, A | Audit only | Use as geometry, control, policy, or label input is prohibited |

The layout hash is Category B: canonicalize `ScenarioLayout.canonical_geometry()`
and apply the frozen SHA-256 document function. Mission direction is Category B:
normalize `goal_center_meters - start_center_meters`, consistent with
`MissionConfig.heading_alignment = predeclared_goal_direction`. Persistent roles,
topology offsets, and unperturbed initial poses are Category B under the topology
registry:

`pose_i = start_center_meters + R(mission_direction) * role_offset_i(initial_topology)`.

No default origin, fixed world heading, headroom-conditioned placement, or KEEP
substitution is permitted.

## Runtime input inventory

| Consumer | Inputs currently required | Available mapping | Classification/status |
|---|---|---|---|
| Legacy simulator reset | `n_agents`, scenario name, seed, `layout.start_center`, `layout.goal`, `layout.obstacle_array` | Phase 8 stores differently named typed descriptors, not a legacy obstacle array | Historical only; publication binding absent |
| Phase 6 forced-topology runtime | `RuntimeConfig`, one robot's local topology metadata, forced topology, `RobotView`, timestamp | Team size and topology metadata are B; each `RobotView` needs own pose/velocity, local peers, local obstacles, goal and mission direction | Controller interface is usable after a scientific world/session exists |
| Phase 7 transition runtime | Team size, source/target topology, fixture name, abstract graph family and execution strategy | Existing entrypoint fabricates open-space state, selects robot 0 as intent source, and uses diagnostic score 1.0 | It has no layout, source snapshot, disturbance, dynamic obstacle, or session input |
| Obstacle sensor boundary | Robot position, global obstacle centers, one common obstacle radius, `R_obs` | Phase 8 circles carry per-primitive radii and corridors are boundary descriptors | Corridor observation/collision source is D1; current helper cannot represent the full schema |
| Communication boundary | Joint poses, per-robot radio/table states, channel queues/RNG, mode/epoch state, range/loss/delay parameters | Nominal runtime values exist; jobs provide a seed and profile identifier | Executable per-episode schedule is D3 |
| Dynamic-obstacle provider | Initial dynamic state, time evolution, post-waypoint behavior, optional observation noise and RNG | Radius, waypoints, a speed parameter and a seed are stored | Evolution law is D2; no provider exists |
| Disturbance provider | Distribution, bounds, injection point, temporal process, RNG state | Job manifest provides deterministic seed identities | Generator semantics are D4; seed alone is not Category C |
| Mission completion evaluator | Goal-region rule, collision history, deadlock rule, transition/protocol/safety validity, Metric V3 dwell, irreversible-progress rule | V4 names ten booleans and the family horizon | Several boolean-producing rules are D6 |
| Counterfactual initialization | Complete source state, protocol/controller state, queues, RNG streams, mission/event state and clone hash | Rollout contract requires byte-identical starts and matched streams | Engineering schema can be added only after D1-D6 are resolved; no source state currently exists |

## Approved initialization and rollout rules

| Frozen source | Rule that can be used | Binding consequence |
|---|---|---|
| `PRIMARY_RUNTIME_INITIAL_TOPOLOGY.md` | COMPACT by default; LINE only for an explicitly declared, physically valid narrow start; KEEP prohibited | Current layouts initialize COMPACT; roles are generated once from the registry |
| Scenario-family contract | Every family starts COMPACT; declared horizon is terminal bound; global world may provide only local observations to robots | Initial topology and horizon are available, but high-level obstacle/profile names do not complete execution semantics |
| Split contract | Train and validation are nonfinal; final-test enumeration and runtime access are gated | This audit inspected train/validation only |
| Counterfactual rollout contract | COMPACT/LINE clones must have identical source state, lifecycle, communication realization, horizon and matched replicas; unchanged candidate has no no-op epoch | Matching requirements are clear, but no cloneable scientific episode state can be constructed yet |
| Decision-state/source contract | S0-S5 names and episode/event allocation are frozen independently of outcomes | Allocation is executable; four source behaviors are not fully specified |
| Phase 6 initial-condition contract | Exact/perturbed fixture formulas are mechanical controller qualification, explicitly not scientific scenario-family construction | It cannot silently supply Phase 9 source perturbations or S5 semantics |

## Category D findings

### D1 - Static corridor and bypass geometry

`straight_corridor`, `polyline_corridor`, and `s_corridor` records do not freeze
wall thickness/radius, boundary offset convention, discretization spacing,
endpoint caps, no-bypass world extent, or analytic-versus-circle collision and
sensing semantics. The legacy `corridor_walls` helper uses historical
obstacle-center collision semantics and a legacy world bound. Selecting it would
change the meaning of nominal passage width and is not an approved derivation.

### D2 - F9 dynamic-obstacle semantics

The nonfinal F9 records are internally inconsistent if both canonical speed and
timestamped waypoints are treated as authoritative:

| layout | declared speed (m/s) | crossing time (s) | speed implied by 5 m waypoint displacement (m/s) |
|---|---:|---:|---:|
| `train-f9-00` | 0.150000 | 12.000000 | 0.416667 |
| `train-f9-01` | 0.163200 | 12.880000 | 0.388199 |
| `validation-f9-00` | 0.201600 | 15.440000 | 0.323834 |

No frozen rule chooses speed versus waypoint timing, specifies interpolation,
defines behavior after the last waypoint, or defines dynamic contact and sensor
semantics. Final-test data was not opened to produce this comparison.

### D3 - Communication realization

F8 stores `delay_s`, `packet_loss`, and a profile name. It does not specify the
loss process, delay distribution/quantization, temporary-disconnection start and
end times, affected links/components, or restoration state. The Phase 7
temporary-disconnection fixture cuts one abstract path edge during a protocol
round; no frozen contract maps that mechanical fixture to an F8 episode.

### D4 - Scientific initial condition and disturbance

Seed namespaces identify initial-condition, communication, dynamic-obstacle and
counterfactual streams, but they do not define distributions, bounds, temporal
processes, stream consumption, or where perturbations enter the dynamics. The
Phase 6 bounded fixtures are explicitly non-scientific qualification fixtures.
Therefore these job seeds cannot yet produce Category C runtime state.

### D5 - Source policies

S1 and S2 uniquely declare fixed COMPACT and fixed LINE topology behavior once a
session exists. S0 has no family/time-specific script. S3 has no frozen
COMPACT/LINE geometric rule; the existing deployable geometric selector is the
historical KEEP/LINE path. S4 has no approved scenario event initiator and score
mapping; the Phase 7 open fixture's robot-0 request and score 1.0 are not bound to
the Phase 8 source contract. S5 has no approved base source, perturbation
distribution, timing, count, or scenario bounds. Implementing S0/S3/S4/S5 would
invent source-state selection semantics.

### D6 - Task evaluator

Target V4 freezes ten required booleans but does not define all executable
predicates that produce them. Missing rules include persistent-deadlock duration
and progress threshold, irreversible-progress loss, the Phase 8 goal-region
threshold, full-horizon dynamic/static collision semantics, and hold/continue
task behavior by family. The legacy environment and Phase 6 qualification use
different task-specific rules; choosing either is not a frozen Phase 8 mapping.

## RB-1 gate

Required start origin, goal center and horizon are uniquely available. The
complete obstacle state, communication state, dynamic-obstacle state,
disturbance state, source-policy state and task-evaluation state are not. Since at
least one required value is Category D, RB-1 requires an immediate stop before
binding schema, publication executor, snapshot/clone implementation, source
policies, execution manifests, or structural canary.
