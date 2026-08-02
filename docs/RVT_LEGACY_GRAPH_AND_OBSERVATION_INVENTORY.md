# RVT Legacy Graph and Observation Inventory

## 1. Scope and provenance

This inventory was completed before Phase 4 implementation changes. The source
baseline is approved Phase 3 commit
`c44389900276d4c98b6c0f4503dbef53218962aa`. It covers the source tree, strict
decentralized namespace, centralized historical runtime, ROS adapter, training
paths, scripts, tests, checkpoint-facing shapes, and the packaged deployment
copy.

The repository contains two incompatible learned-graph families:

- a historical whole-swarm graph with node/edge widths `68/11`;
- a robot-local decentralized ego graph V1 with widths `28/9`.

Neither has a canonical serialized schema version. Tensor width alone is not a
safe migration key.

## 2. Implementation inventory

| Module or function | Purpose | Runtime or training use | Input information | Local or global | Variable N | Variable degree | Obstacles | Topology | Pooling | Known leak or limitation | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `environment.SwarmFormationEnv.observe` | Simulator observation dictionary | Historical runtime, training, evaluation | Complete positions, velocities, obstacles, global context and labels | Global | Yes | N/A | Complete map arrays and per-robot lidar | Legacy action-mode scalar | None | Emits centroid progress, formation error, bottleneck, global arrays and split remnants | Simulation/evaluation boundary only; prohibited input to strict runtime |
| `environment.infer_context` | Global context preprocessing | Historical runtime and dataset | Swarm centroid, team average velocity, complete obstacles | Global | Yes | N/A | Global obstacle-derived bottleneck | None | Mean/min summaries | Global progress and average speed | Centralized diagnostic compatibility only |
| `dataset.build_graph_arrays` / `build_graph` | Historical learned graph | Active historical policy/checkpoint and offline training | Entire observation dict, joint state, complete obstacles, global formation error | Global | Yes | k-NN capped by `graph_k` | Global centroid, global TTC, lidar rows | Five-way legacy one-hot; no persistent role | Downstream graph pooling | Absolute pose, centroid-relative pose, global formation error, global min TTC, out-of-range robots and obstacles | Move behind explicit `legacy_global_graph` adapter; never strict runtime |
| `dataset.collate_graphs` | Historical minibatch disjoint union | Training | Whole-swarm graph samples | Global sample semantics | Yes | Yes | As above | As above | Batch indices feed pooled graph output | No feature-validity masks; each sample is already a complete swarm | Preserve for historical checkpoint reproduction only |
| `models.pooled_graph_features` | Mean graph readout | Historical learned runtime/training | All nodes selected by `batch_index` | Complete input graph | Yes | Yes | Indirectly | Indirectly | Mean via `index_add_` | Produces one team/local-active-set vector and is prohibited in strict namespace | Legacy global model only |
| `models.GraphBackbone` and policy classes | Historical GNN/action/recovery/topology heads | Active historical runtime and training | `68/11` graph tensors | Global under historical dataset | Yes | Yes | Indirectly | Legacy learned vocabulary, topology-conditioned action banks | Multiple whole-graph pooled heads | Model-specific schema; graph-level outputs; old action-head assumptions | Historical checkpoint compatibility; Phase 5 reconstruction required |
| `policy_runtime.batch_from_obs` / `infer_learned_action` | Historical model adapter | Active historical Python and ROS paths | Complete observation dict | Global or locally reconstructed group pretending to be global | Yes | Yes | Complete supplied array | Legacy action vocabulary | Calls historical pooled models | Ambiguous `from .dataset import build_graph`; safety/selection consume global obs | Route through explicit legacy adapter; do not silently switch outputs in Phase 4 |
| `binary_pilot.build_dataset` / `build_action_dataset` | Old binary-label/action datasets | Training only | Complete simulator observation | Global | Fixed study sizes 4/6, constructor itself variable | k-NN | Global | KEEP/LINE labels over global graph | Historical model pooling | Width-based checkpoint assumptions and outcome labels | Preserve offline only; no V2 migration without original local inputs |
| `decentralized.comms.NeighbourTable` | Fresh one-hop received state | Strict runtime | Own state plus received `Beacon` | Local | Yes | Yes | No | Beacon carries only KEEP/LINE role coordinates | None | Correct freshness/order/duplicate handling; no COMPACT role field; scalar peer degree discloses bounded two-hop count | Retain communication authority; V2 consumes emitted `NeighbourRecord`s conservatively |
| `decentralized.comms.simulate_local_obstacles` | Simulator lidar gate | Simulation boundary only | Complete obstacle array plus one robot pose | Global input, local output | Yes | N/A | Emits only local relative discs | None | None | Uses global simulator truth only at explicitly named boundary; no obstacle age/confidence | Retain boundary; V2 compatibility adapter marks tuple observations current and valid |
| `decentralized.comms.simulate_broadcast_round` | Construct per-robot `RobotView`s | Simulation boundary | Joint simulator state, radio model, full obstacles | Global boundary, local outputs | Yes | Yes | Range-gated local tuples | RoleAssignment KEEP/LINE | None | Full state access is intentional boundary; physical beacon schema is binary-role legacy | Retain; no deployable code may call it to recover hidden state |
| `decentralized.ego_graph.build_ego_graph` | Ego graph V1 | Active preserved decentralized selector | One `RobotView`, candidate KEEP/LINE | Local | Yes | Yes | One node per local disc | Candidate KEEP/LINE role coordinate | No graph pooling; center-root consumer | Unversioned, unnormalized raw geometry, input-order serialization, no feature masks, no COMPACT, no lifecycle/timestamp schema | Freeze as `decentralized-ego-v1` compatibility; V2 becomes future authority |
| `decentralized.ego_graph.EgoGraph` | V1 tensor container | Runtime/training | `28/9` tensors | Local | Yes | Yes | Yes | Binary candidate mode | None | No schema/config/topology hash; source IDs are diagnostics only | Preserve for existing checkpoints; explicit non-convertible migration |
| `decentralized.models.EgoTrunk` | Preserved local selectors | Active decentralized selector | V1 ego tensors | Local | Yes | Yes | Through V1 | KEEP/LINE only | Center-node readout | Correct locality but fixed to V1 widths and Phase 5 heads | Do not change in Phase 4; future consumer contract reads V2 root only |
| `decentralized.training.batch_ego` | Disjoint-union V1 batching | Offline training | Sequence of V1 ego graphs | Each sample local | Yes | Yes | Yes | KEEP/LINE batches | Root indices, no pooling here | No explicit graph-index tensor or feature masks; type is generic `object` | Preserve V1 training; V2 batching moves to authoritative module |
| `decentralized.training.simulate_build_team_dataset` | Labelled V1 ego samples | Offline training | Simulator boundary plus global Recovery Event label | Local inputs with global target | Fixed old study sizes 4/6 | Yes | Yes | KEEP/LINE | Distributed-consensus loss later | Label is team-global but not a model feature; imports training layouts | Preserve historical training only; never runtime |
| `decentralized.runtime._robot_decision` | Current decentralized scoring adapter | Strict runtime | One `RobotView` | Local | Yes | Yes | Yes | KEEP/LINE | V1 root readout | Active output would change if V2 replaced V1 | Keep active V1 unchanged; expose V2 separately for Phase 5 |
| `decentralized.epoch.simulate_*` graph calls | Protocol diagnostics using local scores | Simulation/offline portions of protocol | Per-robot views | Local graph inputs | Yes | Yes | Yes | KEEP/LINE | V1 root readout | Uses V1 schema; no COMPACT qualification | Preserve; no protocol redesign in Phase 4 |
| `decentralized.local_controller.local_controller` | Robot-local control observation consumer | Strict runtime | `RobotView`, local peers and obstacles | Local | Yes | Yes | Local discs | Committed KEEP/LINE pairwise roles | None | Not a graph path; controller gains/behavior are frozen | Do not modify |
| `topology_registry.runtime_local_view` | Static local nominal-formation geometry | Mission setup/runtime metadata | One role and nominal topology neighbours | Local static slice | Yes | Nominal sparse degree | No | KEEP/COMPACT/LINE | None | Not an observation graph; cannot represent arbitrary physical peers | Reuse as source for V2 local topology conditioning |
| ROS `formation.estimate_scan_obstacles` | Scan clustering/tracking | Historical ROS runtime | One robot scan and pose | Local sensing | Bounded by `max_obstacles=16` | Variable until truncation | Cluster centroids/velocities | None | None | Fixed maximum without validity mask; outputs world centroids | Keep historical adapter; V2 obstacle contract uses local relative primitives and explicit masks |
| ROS `formation.compute_context` / `build_policy_observation` | Recreate old observation dict | Active historical ROS runtime | Self plus active peer list, scan and obstacles | One-hop active set, but treated as complete graph | Variable active set | Yes | Local scan-derived array | Legacy modes | Historical model pooling | Recomputes active-set centroid, average speed and formation error; schema does not preserve observer/root semantics | Classify centralized/local-group compatibility, not strict V2 runtime |
| ROS `agent_node._active_team` / `_control_step` | Peer filtering and historical inference | Active ROS compatibility | Fresh/range-gated peers plus own sensors | Locally available peers | Yes | Yes | Local scan | Legacy modes | Historical pooled model | Timeout/range defaults `1.0 s/4.0 m` differ from Phase 2 `0.45 s/3.0 m`; computes actions for all active nodes then selects self | Preserve historical deployment; not publication V2 path |
| `deploy/rvt_swarm_ros2_jazzy_bundle/**` | Packaged historical snapshot | Deployment artifact/checkpoint reproduction | Copied old source | Mixed | As copied | As copied | As copied | Legacy | Global pooling copied | Diverges from current source and has no V2 schema | Immutable historical bundle; do not silently edit |
| `scripts/audit_recovery_signal.py` and dataset scripts | Diagnostics/training | Offline only | Global graph and labels | Global | Varies | Varies | Global | Legacy | Historical | Direct ambiguous `dataset.build_graph` imports | Keep offline and identify as legacy in migration report |
| `tests/test_ego_graph_locality.py` | V1 locality evidence | Test only | Actual V1 builder and simulated views | Local | Limited fixtures | Yes | Yes | KEEP/LINE | Synthetic root aggregation | Strong V1 intervention tests but no V2 schema/serialization/COMPACT | Preserve; add independent Phase 4 V2 tests |

## 3. Explicit findings

### Active global-state paths

The root-level `policy_runtime -> dataset.build_graph -> models` path is an
active historical whole-swarm path. The ROS agent reconstructs a whole graph of
its currently active peer set and passes it through the same model. Neither path
is permitted in the strict `rvt_swarm.decentralized` deployable namespace.

`decentralized.runtime` is separate: its active learned selector consumes only
V1 `RobotView` ego graphs and uses a root-node readout. Replacing it during
Phase 4 would be behavior-affecting and is prohibited.

### Whole-swarm and global preprocessing

`dataset.build_graph_arrays` computes or consumes absolute positions, centroid,
obstacle centroid, global formation error, global minimum TTC, complete lidar
rows and k-nearest robots regardless of communication delivery. These tensors
enter historical deployable model code through `policy_runtime`.

### Pooling

`rvt_swarm.models.pooled_graph_features` and several historical heads reduce all
nodes sharing one `batch_index`. With historical inputs this is complete-swarm
pooling. `rvt_swarm.decentralized.models` instead reads `h[center_index]` and has
no pooling operator. Local aggregation over one V2 ego graph remains permitted;
aggregation across ego graphs or over a reconstructed swarm is prohibited.

### Duplicate schemas and fixed assumptions

- Global historical schema: node width 68, edge width 11, legacy five-way mode
  one-hot, no persistent-role feature, no validity mask.
- Decentralized V1 schema: node width 28, edge width 9, binary KEEP/LINE role
  features, no schema hash or general topology registry binding.
- Historical ROS obstacle path truncates at 16 clusters without a validity mask.
- Historical k-NN uses configured `graph_k`; this is a degree cap, not a
  communication contract.
- No existing graph batch carries node-feature or edge-feature validity masks.
- No schema supports KEEP/COMPACT/LINE through one canonical local interface.

### Freshness and missing data

`NeighbourTable` correctly rejects self, future, stale, duplicate and
out-of-order packets and sorts accepted records by sender ID. V1 repeats a
staleness/link gate but accepts obstacle tuples as implicitly current, valid and
complete. Missing obstacle velocity is encoded as zero without a separate
feature-validity mask. The ROS compatibility path uses different timeout and
range defaults from the authoritative Phase 2 configuration.

### Checkpoint and result impact

Historical global checkpoints expect `68/11`; decentralized V1 checkpoints
expect `28/9`. Neither can load a V2 tensor without a model reconstruction.
Phase 4 must therefore leave both active inference outputs unchanged, version
V2 separately, and reject tensor-width-only migration. Historical result files
remain untouched and traceable to their original graph paths.

## 4. Inventory gate

The inventory is complete for every graph/observation builder, active consumer,
batching path, pooling operator, runtime boundary, ROS adapter and packaged copy
found at the approved Phase 3 baseline. Phase 4 implementation may now begin.
