# RVT Legacy Controller and Safety Inventory

Inventory frozen before any Phase 6 controller implementation. Repository
baseline: `b47a95fe238550e7fb7492c6fafd8427c1b572ec`.

## Runtime boundaries

The only pre-Phase-6 controller in the strict decentralized runtime is
`rvt_swarm.decentralized.local_controller.local_controller`. It accepts one
`RobotView` and returns one acceleration. `simulate_broadcast_round` is the
explicit simulator boundary that discovers neighbours from joint simulator
state and reduces them to one-hop views. `environment.step` remains a
centralized simulation integrator and collision resolver; it is not a
deployable controller.

The root-level controller, safety, baseline, learned-policy and ROS paths are
historical, diagnostic, training, or deployment-compatibility paths. They are
not valid inputs to the new strict robot-local controller namespace.

## Controller and safety paths

| Module or function | Purpose | Runtime status | Inputs | Local or global | Action semantics | Topology support | Variable-N | Obstacle support | Safety mechanism | Known defect | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `decentralized.local_controller.local_controller` | Existing pairwise formation, goal and avoidance controller | active in pre-Phase-6 decentralized runtime | one `RobotView`, runtime config, committed mode | robot-local | own planar acceleration | KEEP, LINE only | yes | local relative circles | reactive clearance/TTC plus norm clipping | monolithic terms; no COMPACT; no explicit projection or typed diagnostics; imports private kernels from global controller | supersede for forced-topology qualification; preserve historical runtime unchanged |
| `decentralized.local_controller.local_formation_error` | Pairwise displacement residual | active helper | one `RobotView` | robot-local | formation error in meters | KEEP, LINE only | yes | no | none | uses all valid communication peers rather than only registry formation edges; role wrapper cannot select COMPACT | replace with registry-sliced local formation term |
| `decentralized.roles.RoleAssignment` and pairwise helpers | Persistent role geometry | active mission setup and local runtime | persistent IDs, static role offsets, mission direction | local after setup; one explicitly named simulation setup boundary is global | geometry only | KEEP, COMPACT, LINE templates exist | yes | no | none | legacy `RobotView`/beacon carries KEEP and LINE offsets only | reuse registry and Phase-4 local topology slices; do not change roles |
| `decentralized.comms.NeighbourTable` | Ingest one-hop beacon state and reject stale records | active deployable communication path | own state and received beacon bytes | robot-local | no action | KEEP/LINE wire fields | yes | no | stale exclusion | current wire schema does not carry COMPACT geometry | preserve protocol; Phase 6 adapter consumes already prepared local topology metadata |
| `decentralized.comms.simulate_broadcast_round` | Simulator neighbour discovery and local-view construction | simulation boundary | complete simulator positions, velocities and obstacles | global simulation infrastructure | no action | KEEP, LINE runtime views | yes, with global scan cost | range-gated local circles | none | centralized O(N^2) discovery is not deployable cost | preserve and report separately; provide received-message adapter |
| `decentralized.runtime.simulate_decentralized_episode` | Existing selection/epoch/control simulation | simulation boundary | environment, protocol state and local views | local actions inside global orchestrator | joint array assembled from own actions | online KEEP/LINE transitions | experimental N=6 | local controller obstacles | old reactive controller and environment collision response | transition protocol and model-selector branches are out of Phase 6 scope | leave unchanged |
| `controllers.expert_action` | Historical expert and training target | training/centralized diagnostic | complete observation dictionary | global | joint N x 2 acceleration | historical action IDs | yes, but global | full obstacle array | reactive clearance and TTC, final clipping | reads centroid, full formation error, all robots and all obstacles; returns joint action | historical only; prohibited from strict controller namespace |
| `controllers._desired_offsets` and `_project_topology_state` | Historical topology geometry and action interpretation | centralized helper | full joint positions and environment context | global | geometry/state projection | legacy KEEP, compress, LINE, split, recover actions | partly | no | none | duplicates topology geometry, runtime sorting and legacy IDs outside registry | historical only |
| `controllers._clearance_term`, `_ttc_term` | Reactive repulsion kernels | used by old global and local controllers | relative position/velocity | locally computable | dimensionless vector terms | topology-independent | yes | yes | reactive only | private helpers mix no explicit physical units or projection guarantee | do not import into Phase 6 controller |
| `safety.simple_recover_shield` | Historical learned-policy safety filter | learned-policy runtime only | joint actions, full observation, recoverability scores | global activation and orchestration | modifies joint N x 2 acceleration | legacy topology context | yes | full obstacle array | per-robot small QPs after global risk trigger | global collision risk and centroid progress; can use learned scores; blends projection; not strict-local | preserve historical results; prohibit from Phase 6 |
| `safety._build_cbf_constraints` | Historical per-robot constraint builder | helper for old filter/baseline | complete joint observation | global preprocessing | half-spaces over one robot action | topology-independent | yes | all obstacles | first-order CBF-labelled constraints | scans all robots/obstacles; semantics do not match the simulator's semi-implicit acceleration update exactly | diagnostic reference only |
| `safety._solve_per_robot_qp` | Historical two-dimensional active-set solver | helper for old filter/baseline | nominal action and constraint list | per-robot decision variable after global preprocessing | bounded own acceleration | independent | yes | indirect | disk and half-space projection | infeasible set returns clipped target without declaring failure, which can be unsafe | do not reuse as authoritative projection |
| `safety.collision_risk`, `progress_direction`, `estimated_form_rms` | Historical filter trigger/features | learned-policy and audit paths | complete observation | global | diagnostics | legacy | yes | full obstacle array | reports predicted/global risk | centroid/global metrics are prohibited control inputs | offline/legacy only |
| `baselines.orca` | RVO2 baseline | centralized diagnostic baseline | complete observation | global orchestration | joint accelerations derived from preferred velocities | heuristic KEEP/LINE | yes | full obstacle array | ORCA solver | global state; external solver; not authoritative local stack | preserve diagnostic baseline |
| `baselines.orca_like` | Lightweight historical approximation | centralized diagnostic baseline | complete observation | global | joint acceleration | heuristic | yes | full array | heuristic repulsion | name and mechanics are historical; no formal ORCA semantics | historical only |
| `baselines.cbf_qp` | Historical CBF-QP baseline | centralized diagnostic baseline | complete observation | global preprocessing, per-robot solve | joint array of bounded accelerations | heuristic | yes | full array | old CBF helper/QP | all-robot/all-obstacle scan and unsafe undeclared infeasible fallback | historical only |
| `baselines.cbf_qp_like` | Heuristic safety baseline | centralized diagnostic baseline | complete observation | global | joint acceleration | heuristic | yes | full array | potential response/clipping | not a validated CBF-QP | historical only |
| `baselines.fixed_formation_expert`, `adaptive_formation` | Historical centralized formation baselines | diagnostic | complete observation | global | joint acceleration | legacy action semantics | yes | full array through expert | reactive | inherits centroid, duplicated geometry and global obstacle access | historical only |
| `baselines.centralized_mpc` | Predictive baseline | centralized diagnostic | complete state and cloned environment | global | joint action sequence search | legacy candidates | bounded by explicit budget | global | predictive rollout collision cost | joint optimization and future simulator truth | centralized reference only |
| `policy_runtime.infer_learned_action` | Historical learned action adapter | learned-method runtime and ROS compatibility | global graph batch and model outputs | global graph preprocessing | joint N x 2 acceleration | legacy vocabulary | model-dependent | old safety filter | optional global filter | learned full actions and Phase-5-incompatible checkpoints | isolated historical path; never import into Phase 6 |
| `models.*` and binary/simplified action heads | Historical learned controllers and classifiers | training/checkpoint compatibility | global or legacy local graphs | mostly global or semantically incompatible | joint or graph-associated actions | ambiguous legacy vocabularies | mixed | learned features | learned output only | incompatible with `rvt-ego-graph/v2`; some direct-action heads use sparse targets | historical/ablation only |
| `environment.step` | Simulator action execution | active centralized simulator | joint N x 2 action array and one team topology action | global simulation infrastructure | planar acceleration in m/s^2 | legacy environment bookkeeping IDs | yes | full simulator geometry | acceleration norm clip, speed clip, post-integration collision resolution | single team topology argument; hidden duplicate action clipping; collision response occurs after contact and is not a controller guarantee | preserve behavior; Phase 6 mirrors and tests dynamics semantics without changing history |
| `environment._resolve_collisions` | Hard overlap response | active simulator only | complete positions, velocities, obstacles | global | position/velocity correction after action | independent | yes | all obstacles | three global resolution sweeps | safety violation is already physically reached before correction; centralized and nondeployable | simulator-only; never claim as local safety |
| `environment.desired_offsets`, `apply_topology` | Legacy simulator topology bookkeeping | active simulator | joint state and legacy action ID | global | no direct action | no canonical COMPACT ID 5 | yes | scenario context | none | duplicates geometry, sorts joint state and conflates topology with legacy actions | do not use for Phase 6 forced topology |
| `EpisodeAccumulator`, Metric V3 and evaluation utilities | Offline scoring | evaluation only | trajectory/joint state | global permitted offline | metrics only | KEEP, COMPACT adapter, LINE | yes | global collision metrics | detects violations after occurrence | must never enter controller input | retain offline only |
| qualification scripts under `scripts/qualify_local_controller*` | Historical KEEP/LINE mechanical probes | offline | global environment and scripted transitions | global orchestrator | invokes old local actions | KEEP/LINE, N=6 emphasis | limited | fixture-specific | old controller/environment response | prior geometry and transition scope differ from Phase 6 | preserve prior reports; do not overwrite |
| ROS `formation.action_to_twist` | Differential-drive bridge | ROS compatibility runtime | one planar acceleration and current velocity | local bridge after global policy in current node | acceleration integrated to desired velocity, then Twist | legacy | one robot per node | scan used upstream | actuator clipping | ROS agent currently obtains global policy result and is not Phase-6-qualified | document only; no ROS changes in Phase 6 |
| `deploy/rvt_swarm_ros2_jazzy_bundle` | Frozen deployment bundle | historical artifact | copied legacy modules | mixed | copied legacy behavior | legacy | mixed | mixed | copied old filter | duplicate source snapshot, not authoritative workspace code | do not edit |

## Confirmed defects and incompatibilities

- Active historical `expert_action`, learned policy, ORCA, CBF-QP and MPC paths
  accept complete joint observations and return joint action arrays.
- Centroid and global formation error are used by the root controller,
  historical safety trigger, environment bookkeeping and offline metrics. Only
  offline metrics and simulator bookkeeping are permitted to retain them.
- The old safety filter performs global risk activation and global constraint
  construction even though its final optimization variable is per robot.
- The old QP helper has an undeclared unsafe fallback when its constraints are
  infeasible.
- Existing runtime collision resolution is a post-contact simulator response,
  not preventive safety.
- Legacy environment/controller topology geometry is duplicated outside the
  registry and does not understand canonical COMPACT ID 5.
- Existing strict local formation control uses every received peer rather than
  the topology registry's nominal local formation edges.
- Controller clipping occurs in the old local controller and again in
  `environment.step`; learned policy and several baselines also clip actions.
- Controller gains are duplicated in legacy `Config`, immutable
  `RuntimeConfig`, ROS parameters and archived deployment copies.
- Previous reconfiguration qualification utilities are N=6 transition tests
  and cannot establish fixed-topology control through N=24.
- Runtime code does not import evaluation utilities, but the centralized
  simulator necessarily computes global metrics after each action.

## Phase 6 disposition

Phase 6 will add a separate authoritative forced-topology robot-local stack
using immutable `RuntimeConfig`, registry-produced robot-local topology slices,
fresh one-hop states and local obstacle primitives. Existing controller,
environment, learned-policy, protocol, ROS and historical result paths remain
unchanged. The new safety projection will solve only for one robot's planar
acceleration and will expose infeasibility and fallback status explicitly.
