# RVT Existing Configuration Inventory

## 1. Audit scope

This is the Phase 2A inventory taken at approved Phase 1 commit
`ed7c72771a25a3797a8c14f75119451e84adc0e5`. It was completed before any
Phase 2 code change.

The inventory covers:

- repository dataclasses and constructor defaults;
- deployable decentralized modules and their simulator boundary;
- legacy centralized runtime, training, validation, and evaluation modules;
- module-level constants and derived values;
- CLI defaults, ROS 2 parameters, YAML/JSON manifests, and frozen fixtures;
- active duplicates, compatibility paths, and result-only records.

"Runtime" below means a value can affect a robot-local decision, protocol
state, communication admission, or actuator command. "Evaluation" includes
simulation, training, validation, diagnostics, and offline metrics. Historical
result JSON files are records, not active configuration sources.

## 2. Use-site sets

The table abbreviations below expand to all current Python use-site groups found
by AST attribute scanning and direct symbol search.

| ID | Current use sites |
|---|---|
| `U-ENV` | `environment.py`, `dataset.py`, `controllers.py`, `baselines.py`, `safety.py`, `regions.py`, `recoverability.py`, `recovery_v2.py`, `evaluate.py`, `visualize.py`, `binary_pilot.py` |
| `U-LOCAL` | `decentralized/local_controller.py`, `epoch.py`, `runtime.py`, `ego_graph.py`, `comms.py`, `consensus.py` |
| `U-OFFLINE` | `decentralized/formation_metric_v3.py`, `reconfiguration_metrics.py`, `qualification_fixtures.py`, `env_geometry.py`, `comm_cost.py`, `training.py` |
| `U-EXP` | `scripts/post_parameter_repair_regression.py`, `post_repair_traces.py`, `golden_episode_trace.py`, `local_exit_observability_audit.py`, reconfiguration qualification scripts, smoke/validation scripts |
| `U-TRAIN` | `train.py`, `dataset.py`, `binary_pilot.py`, `models.py`, `scripts/train_*.py`, `run_experiments.py` |
| `U-EVAL` | `evaluate.py`, `metrics.py`, `consistency.py`, `provenance.py`, `visualize.py`, evaluation/aggregation scripts |
| `U-ROS` | `ros2_ws/src/rvt_swarm_ros/rvt_swarm_ros/agent_node.py`, `formation.py`, `experiment_monitor.py`, launch/config files |

## 3. Repository-wide mutable configuration

All records in this section are currently defined in `rvt_swarm/config.py` as
mutable dataclasses. `Config` contains runtime, training, evaluation, method,
seed, and audit sections in one object; decentralized functions currently
accept this broad object and read `cfg.env`.

### 3.1 Environment and physical values

| Parameter | Current definition location | All use sites | Semantic meaning | Units | Runtime or evaluation only | Configured or derived | Current default | Duplicate definitions | Current source of truth | Required action |
|---|---|---|---|---|---|---|---|---|---|---|
| `world_size` | `config.EnvConfig` | `U-ENV`, `U-OFFLINE`, `U-EXP` | Simulator square-world extent | m | Evaluation/simulation | Configured | `12.0` | Fixture world `18.0` | `EnvConfig` per run | Move to evaluation/simulator config; fixture override remains explicit |
| `dt` | `config.EnvConfig` | `U-ENV`, `U-LOCAL`, `U-OFFLINE`, `U-EXP`, `U-ROS` | Control integration period | s | Runtime and evaluation | Configured | `0.15` | `CommParams.t_ctrl`, `PlatformParams.control_period`, ROS `control_rate_hz` | Conflicting | Authoritative `control_period_seconds`; derive steps/rates |
| `max_steps` | `config.EnvConfig` | `environment.py`, `evaluate.py`, `recovery_v2.py`, `U-OFFLINE`, `U-EXP` | Episode horizon | steps | Evaluation only | Configured | `120` | Fixture `260`, script horizons | Per experiment | Keep in evaluation config; never robot runtime |
| `robot_radius` | `config.EnvConfig` | `U-ENV`, `U-LOCAL` through parameters, `U-OFFLINE`, diagnostics | Physical robot radius | m | Runtime and evaluation | Configured | `0.18` | `PlatformParams.robot_radius`, ROS platform geometry | `EnvConfig` | Authoritative physical config; frozen value |
| `obstacle_radius` | `config.EnvConfig` | `U-ENV`, `U-OFFLINE`, `U-EXP` | Simulator point/disc obstacle radius | m | Evaluation and local sensor records | Configured | `0.35` | Fixture and ROS obstacle geometry | `EnvConfig`/layout | Separate simulator obstacle geometry from safety clearance |
| `sensing_radius` | `config.EnvConfig` | `baselines.py`, `controllers.py`, `dataset.py`, `safety.py`, `local_controller.py` | Legacy peer/general sensing envelope | m | Runtime and evaluation | Configured | `4.0` | `CommParams.r_sense` | Conflicting | Authoritative sensing config; mark legacy semantics |
| `max_speed` | `config.EnvConfig` | `U-ENV`, `local_controller.py`, `epoch.py`, `parameters.py`, `U-EXP`, `U-ROS` | Maximum translational speed | m/s | Runtime and evaluation | Configured | `0.9` | `PlatformParams.max_speed`, ROS twist limit `0.22` for a different platform adapter | Conflicting by platform | Authoritative physical config; ROS path remains deprecated |
| `max_accel` | `config.EnvConfig` | `U-ENV`, `local_controller.py`, `parameters.py`, `policy_runtime.py`, diagnostics | Maximum planar acceleration | m/s^2 | Runtime and evaluation | Configured | `0.6` | `PlatformParams.max_accel` | Duplicate | Authoritative physical config; frozen value |
| `goal_tolerance` | `config.EnvConfig` | `environment.py`, `regions.py`, `visualize.py`, diagnostics | Goal-reaching radius | m | Evaluation only in current decentralized path | Configured | `0.55` | Script/report copies | `EnvConfig` | Move to mission/evaluation boundary, preserve value |
| `formation_tolerance` | `config.EnvConfig` | `U-ENV`, `epoch.py`, `reconfiguration_metrics.py`, scripts | Formation acceptance tolerance | m | Runtime trigger and evaluation | Configured | `0.55` | `MissionParams.formation_tolerance`, `EPSILON_FORM` | Three active sources | Store ratio/source once; derive frozen `0.55 m` |
| `nominal_spacing` | `config.EnvConfig` | `U-ENV`, `U-LOCAL`, `U-OFFLINE`, `U-EXP` | Formation lattice pitch | m | Runtime and evaluation | Configured | `0.9` | `MissionParams.nominal_spacing`, manifests | Duplicate | `EnvConfig` plus copied mission default | Authoritative formation config; frozen value |
| `min_rr_distance` | `config.EnvConfig` | `U-ENV`, `local_controller.py`, `U-OFFLINE`, diagnostics | Required robot-center separation | m | Runtime and evaluation | Configured | `0.40` | `PlatformParams.collision_clearance_robot` | Duplicate derived/explicit | Derive from radius and inter-robot margin |
| `min_ro_distance` | `config.EnvConfig` | `U-ENV`, `local_controller.py`, `epoch.py`, `U-OFFLINE`, diagnostics | Required robot-center to obstacle-center separation | m | Runtime and evaluation | Configured | `0.55` | `PlatformParams.collision_clearance_obstacle` | Duplicate derived/explicit | Derive from radius and obstacle clearance margin |
| `spacing_margin` | `config.EnvConfig` | `EnvConfig.min_formation_scale` | Extra spacing above collision threshold | m | Runtime in legacy adaptive topology | Configured | `0.05` | None | `EnvConfig` | Formation config; frozen legacy behavior |
| `min_formation_scale` | `EnvConfig` property | `environment.py`, `controllers.py`, split diagnostics | Minimum collision-compatible formation scale | ratio | Legacy runtime/evaluation | Derived | `(min_rr_distance + spacing_margin) / nominal_spacing`, clipped | Former independent implementations repaired | Property | One canonical derivation; compatibility property only |
| `spawn_jitter` | `config.EnvConfig` | `environment.reset` via config state | Initial-condition position noise | m std. dev. | Evaluation only | Configured | `0.12` | Fixture `SPAWN_JITTER=0.06` | Per scenario/fixture | Evaluation config; preserve manifests |
| `obstacle_count` | `config.EnvConfig` | `environment.py` | Static simulator obstacle count | count | Evaluation only | Configured | `8` | Layout-specific geometry | Legacy environment | Deprecate for explicit layouts where possible |
| `dynamic_obstacle_count` | `config.EnvConfig` | `environment.py` | Dynamic obstacle count | count | Evaluation only | Configured | `2` | Layout-specific geometry | Legacy environment | Evaluation config |
| `dynamic_obstacle_speed` | `config.EnvConfig` | `environment.py`, `baselines.py` | Dynamic obstacle speed | m/s | Evaluation only | Configured | `0.35` | Scenario definitions | Legacy environment | Evaluation config |
| `lidar_num_rays` | `config.EnvConfig` | `environment.py`, `dataset.py`, manifests | Simulated lidar resolution | rays | Runtime sensor assumption/evaluation | Configured | `36` | Visualization `36`, ROS sensor publishes its own size | Duplicate display copy | Sensing config; preserve value |
| `lidar_range` | `config.EnvConfig` | `environment.py`, `dataset.py`, `parameters.py`, ROS scan cap | Obstacle sensing range `R_obs` | m | Runtime and evaluation | Configured | `3.0` | `CommParams.r_obs`, `PlatformParams.obstacle_sensor_range`, visualization `3.0` | Four copies | Authoritative sensing config; frozen value |
| `lidar_fov` | `config.EnvConfig` | `environment.py`, `visualize.py`, manifest | Lidar field of view | rad | Runtime sensor assumption/evaluation | Configured | `4.712389` | ROS sensor metadata | `EnvConfig` | Sensing config; preserve approximation |
| `team_sizes` | `config.EnvConfig` | dataset/evaluation/visualization, `run_experiments.py` | Legacy benchmark team-size sweep | count list | Training/evaluation only | Configured | even sizes `2..24` | split constants, decentralized max `6` | Conflicting scopes | Evaluation config; not deployable team size |
| `scenarios` | `config.EnvConfig` | dataset/evaluation/scripts | Legacy scenario sweep | identifiers | Training/evaluation only | Configured | four legacy scenarios | split/layout families and fixture lists | Multiple experiment scopes | Evaluation config; not robot runtime |

### 3.2 Seeds, training, evaluation, audit, and legacy method flags

These fields are not permitted dependencies of deployable RVT-FD runtime.

| Parameter record | Current definition location | All use sites | Semantic meaning | Units | Runtime or evaluation only | Configured or derived | Current default | Duplicate definitions | Current source of truth | Required action |
|---|---|---|---|---|---|---|---|---|---|---|
| `SeedConfig.model_seed` | `config.py` | model builders, training scripts | Model initialization/batch seed | integer seed | Training only | Configured | `0` | CLI positional seed | `SeedConfig`/CLI override | Training config only |
| `training_data_seed` | `config.py` | dataset generation | Training episode seed | integer seed | Training only | Configured | `0` | split seed derivation | `SeedConfig` | Preserve split provenance |
| `validation_seed` | `config.py` | validation | Validation episode seed | integer seed | Validation only | Configured | `0` | split seed base | `SeedConfig` | Evaluation/training boundary |
| `final_test_seed` | `config.py` | final evaluation | Locked final-test seed | integer seed | Evaluation only | Configured | `0` | CLI/manifest copies | Manifest plus `SeedConfig` | Keep out of training/runtime |
| `counterfactual_rollout_seed` | `config.py` | label generation | Counterfactual rollout seed | integer seed | Training only | Configured | `0` | script defaults | `SeedConfig` | Training config only |
| `environment_noise_seed` | `config.py` | future noise path/manifests | Environment noise seed | integer seed | Evaluation only | Configured | `0` | manifest copies | `SeedConfig` | Evaluation config only |
| `TrainConfig.seed` | `config.py` | old checkpoints/CLI | Deprecated overloaded seed | integer seed | Training only | Configured | `42` | all explicit seed roles | Deprecated duplicate | Compatibility only | Preserve for unpickling; never active |
| `device`, `n_workers` | `TrainConfig`, CLI | `U-TRAIN` | Training execution resources | string/count | Training only | Configured | `cpu`, `0` | CLI `auto`/worker defaults | CLI materialization | Training config only |
| `expert_episodes`, `batch_size` | `TrainConfig`, smoke/pilot CLI | `U-TRAIN` | Dataset/training batch budget | episodes/samples | Training only | Configured | `500`, `32` | smoke `30/32`, pilot constants | Per experiment | Serialize training section |
| `epochs`, method-specific epoch fields | `TrainConfig`, pilot constants | `U-TRAIN` | Optimizer epoch budgets | epochs | Training only | Configured | `30`, method fields `300` | smoke/pilot constants | Per experiment | Consolidate only when those legacy trainers migrate |
| `lr`, `weight_decay` | `TrainConfig`, pilot constants | `U-TRAIN` | Optimizer parameters | unitless | Training only | Configured | `3e-4`, `1e-5` | pilot module constants | Per trainer | Training config; legacy copies deprecated |
| `hidden_dim`, `message_passes` | `TrainConfig`, model constructors | `U-TRAIN`; model loading | Legacy learned model shape | count | Training/model artifact | Configured | `128`, `3` | decentralized selector `96`, `3` | Model family specific | Separate legacy and decentralized ModelConfig |
| `recover_horizon`, `graph_k` | `TrainConfig` | dataset/model training | Legacy rollout horizon/graph degree | steps/count | Training only | Configured | `14`, `6` | Recovery V2/script defaults | `TrainConfig` | Training config only |
| early-stopping fields | `TrainConfig`, pilot constants | `U-TRAIN` | Selection stopping rule | epochs/loss | Training/validation | Configured | `40`, `1e-4`, save-best true | smoke/pilot copies | Per protocol | Training config and manifest |
| rollout-validation fields | `TrainConfig`, CLI/scripts | train/evaluate/checkpoint selection | Validation cadence, cells, recheck budget | mixed | Validation only | Configured | interval `10`, episodes `4/8`, top-k `5`, offset `80000` | smoke/pilot copies | Per experiment | Training/validation config; never runtime |
| `hyperparameter_trials` | `TrainConfig` | budget report/tests | Declared tuning budget | trials | Training only | Configured | `0` | report copies | `TrainConfig` | Preserve provenance |
| `EvalConfig.episodes_per_setting` | `config.py`, CLI | `evaluate.py`, `run_experiments.py` | Evaluation episode count | episodes | Evaluation only | Configured | `25` | smoke `3`, manifests | Per experiment | Evaluation config only |
| `AuditConfig` fields | `config.py` | `safety.py`, audit scripts | Legacy selector/safety diagnostic overrides | mixed | Training/evaluation diagnostic | Configured | `None/False/lexicographic/0/...` | script-specific sweeps | `AuditConfig` | Keep deprecated/offline; prohibit runtime import |
| `MethodConfig` fields | `config.py` | legacy policy/safety/environment | Legacy ablation switches | booleans | Legacy centralized runtime/evaluation | Configured | all true | script copies | `MethodConfig` | Deprecated for RVT-FD runtime |
| topology action maps | `config.py` | environment/controller/model/dataset | Legacy action IDs and learned subset | enum IDs | Legacy runtime/training/evaluation | Configured static | IDs `0..4`, learned `[0,2,3]` | decentralized KEEP/LINE constants | Conflicting architectures | Preserve legacy; Phase 3 owns new registry |

## 4. Existing decentralized parameter fragments

### 4.1 `decentralized/parameters.py`

| Parameter | Current definition location | All use sites | Semantic meaning | Units | Runtime or evaluation only | Configured or derived | Current default | Duplicate definitions | Current source of truth | Required action |
|---|---|---|---|---|---|---|---|---|---|---|
| `PlatformParams.robot_radius` | `parameters.py` | derivations/manifests | Robot radius | m | Runtime | Copied | from `EnvConfig` | `EnvConfig.robot_radius` | Env adapter | Consolidate into authoritative physical config |
| `collision_clearance_obstacle` | `parameters.py` | sector/lookahead/support checks | Required obstacle-center clearance | m | Runtime | Copied | `0.55` from env | `min_ro_distance` | Env adapter | Derive from geometry/margin |
| `collision_clearance_robot` | `parameters.py` | support checks/reporting | Required robot-center clearance | m | Runtime | Copied | `0.40` from env | `min_rr_distance` | Env adapter | Derive from radius/margin |
| `max_speed`, `max_accel` | `parameters.py` | lookahead/manifests | Motion bounds | m/s, m/s^2 | Runtime | Copied | `0.9`, `0.6` | `EnvConfig` | Env adapter | Physical config |
| `obstacle_sensor_range` | `parameters.py` | sector support/lookahead | `R_obs` | m | Runtime | Copied | `3.0` | env lidar, `CommParams.r_obs` | Env adapter | Sensing config |
| `communication_range` | `PlatformParams.from_env_config` | manifests/ratios | Radio range | m | Runtime | Constructor literal | `3.0` | `CommParams.r_comm` | No valid single source | Remove hard-code; communication config |
| `control_period`, `communication_period` | `parameters.py` | time derivations | Runtime periods | s | Runtime | Copied/hard-copied | both `env.dt=0.15` | `CommParams.t_*` | Conflicting | Physical and communication config |
| `MissionParams.nominal_spacing` | `parameters.py` | roles/sector/support | Formation spacing | m | Runtime | Constructor default | `0.9` | `EnvConfig` | Duplicate | Formation config |
| `formation_tolerance` | `parameters.py` | support/ratios | Frozen epsilon_form | m | Runtime/evaluation | Constructor default | `0.55` | env and Metric V3 | Duplicate | Derived formation tolerance |
| `recovery_dwell_seconds` | `parameters.py` | dwell derivation/manifests | Required KEEP dwell | s | Runtime semantics/evaluation metric | Configured | `3.0` | `L_RECOVER=20` | Split seconds/steps | Mission config; derive steps only |
| `safety_margin` | `parameters.py` | sector/lookahead | Added transition clearance | m | Runtime | Configured | `0.0` | Fixture `SAFETY_MARGIN=0.3` has different IC meaning | `MissionParams` | Rename semantic margin explicitly |
| `ProtocolParams.max_team_size` | `parameters.py` | diameter/support/manifests | Maximum protocol team size | count | Runtime | Configured | `6` | Env benchmark up to 24 | Conflicting scopes | Authoritative protocol config, generic validation |
| `max_component_diameter` | `parameters.py` | diameter derivation | Declared topology diameter bound | hops | Runtime assumption | Configured optional | `None` | script local diameter | `ProtocolParams` | Preserve optional source; validate against team/max size |
| `max_message_age_seconds` | `parameters.py` | stale-step derivation | Maximum accepted age | s | Runtime | Configured | `0.45` | `CommParams.delta_stale_steps=3` | Seconds vs steps duplicate | Communication config; derive with communication period |
| `evidence_persistence_seconds` | `parameters.py` | trigger derivation | Required continuous opening evidence | s | Runtime | Configured | `0.45` | `L_TRIGGER=3` | Seconds vs steps duplicate | Protocol config; remove step source |
| `event_collection_seconds` | `parameters.py` | lookahead | Event collection latency | s | Runtime assumption | Configured | `0.0` | Implicit scheduling | `ProtocolParams` | Protocol config and documented boundary behavior |
| `commitment_seconds` | `parameters.py` | commitment derivation | Post-decision lock duration | s | Runtime | Configured | `1.5` | `ConsensusParams.h_commit=10`, Recovery V2 default | Three sources | Protocol config; derive steps |
| `rearm_inactive_seconds` | `parameters.py` | lifecycle derivation | Inactive time before rearm | s | Runtime | Configured | `3.75` | `decision_interval=25`, former step constant | Duplicate semantics | Protocol config; derive steps |
| connectivity text | `parameters.py` | docs/manifests | Connectivity claim | text | Runtime assumption | Configured | per-component statement | `LINK_ASSUMPTIONS` | Duplicate prose | Communication/protocol enum plus documentation |
| `steps_from_seconds` | `parameters.py` | all time derivations | Ceiling time-to-step conversion | s/s -> steps | Runtime/evaluation | Derived | `ceil(seconds/period-1e-12)` | Several fixed step constants | Partial source | Retain one versioned derivation |
| recovery/evidence/collection/commit/rearm steps | `parameters.py` | epoch/manifests | Physical durations in discrete rounds | steps | Runtime | Derived | `20/3/0/10/25` | constants elsewhere | Partial source | Centralize in one `DerivedConfig` |
| message-age steps | `parameters.py` | manifest only | Freshness in communication rounds | steps | Runtime | Derived incorrectly from control period | `3` | `CommParams.delta_stale_steps` | Defect masked because periods equal | Derive from communication period |
| component diameter | `parameters.py` | trigger/support/manifests | Worst-case path length | hops | Runtime | Derived | `max_component_diameter or max_team_size-1` | script copies | `parameters.py` | Central derivation and validation |
| `k_trigger` | `parameters.py` | epoch/manifests | Trigger propagation rounds | rounds | Runtime | Derived | diameter (`5`) | `ConsensusParams.k_trigger=5` | Duplicate | Generalize as `k_intent`; keep compatibility alias |
| forward-sector width | `parameters.py` | epoch/manifests | Role-specific future expansion observation band | m | Runtime | Derived | role dependent (`0.55/1.45` at N=6) | fallback `1.45` | Derivation | Retain; add controller/latency assumptions metadata |
| lookahead distance | `parameters.py` | runtime geometric rule/manifests | Required reaction/protocol distance capped by sensor | m | Runtime | Derived | `1.755` nominal | old spacing literal removed | Derivation | Retain one versioned derivation; validate acceleration/sensing |
| `default_parameters` | `parameters.py` | epoch/runtime/scripts | Implicit bundle factory | mixed | Runtime | Constructor fallback | defaults through `Config().env` | all fragments | Hidden bypass | Replace with authoritative default/config adapter |

### 4.2 Communication, consensus, controller, model, lifecycle, and metrics

| Parameter | Current definition location | All use sites | Semantic meaning | Units | Runtime or evaluation only | Configured or derived | Current default | Duplicate definitions | Current source of truth | Required action |
|---|---|---|---|---|---|---|---|---|---|---|
| `CommParams.r_comm` | `system_model.py` | `comms.RadioChannel`, runtime, reports | Communication radius | m | Runtime | Constructor default | `3.0` | Platform hard-code, ROS `4.0` | `CommParams` in current decentralized runtime | Communication config |
| `CommParams.r_sense` | `system_model.py` | definition/report only | Peer sensing radius | m | Runtime assumption | Constructor default | `4.0` | `EnvConfig.sensing_radius` | Duplicate unused | Sensing config; validate or deprecate |
| `CommParams.r_obs` | `system_model.py` | obstacle synthesis/ego admission | Obstacle sensing radius | m | Runtime | Constructor default | `3.0` | Env lidar/platform | Duplicate | Sensing config |
| `delta_stale_steps` | `system_model.py` | comms/ego/epoch/consensus/runtime | Message freshness | steps | Runtime | Constructor default | `3` | protocol seconds/derived function/function defaults | Multiple active sources | Property of derived config only |
| `t_comm`, `t_ctrl` | `system_model.py` | reports/accounting | Periods | s | Runtime | Constructor default | `0.15`, `0.15` | Env/platform | Duplicate | Canonical periods |
| link symmetry/loss/delay/offset | `CommParams` | radio simulator/runtime stress | Link model | bool/probability/steps | Simulation of runtime communication | Configured | true/0/0/0 | scripts construct overrides | `CommParams` | Immutable communication config; delay in seconds plus derived rounds |
| `ConsensusParams.k_score` | `system_model.py` | runtime/epoch/accounting | Score consensus rounds | rounds | Runtime | Constructor default/validation-selected | `4` | `K_SCORE_GRID`; below default diameter 5 | Correctness discrepancy | Require at least diameter; record behavior change |
| `k_trigger`, `k_confirm` | `system_model.py` | runtime/epoch | Intent and confirmation propagation | rounds | Runtime | Constructor defaults | `5`, `5` | derived diameter | Duplicate | Derived or validated optional rounds |
| `h_commit` | `system_model.py` | epoch/runtime | Commitment lock | control steps | Runtime | Constructor default | `10` | commitment seconds, Recovery V2 default | Duplicate | Derived property only |
| `decision_interval` | `system_model.py` | ego normalization, diagnostics | Legacy forced cadence/reference horizon | control steps | Runtime feature/legacy diagnostics | Constructor default | `25` | rearm inactive duration | Ambiguous duplicate | Rename/reference physical duration; no forced cadence |
| `confirm_margin` | `system_model.py` | commitment gate | Minimum score separation | score units | Runtime | Configured | `0.0` | Audit hysteresis has different meaning | `ConsensusParams` | Protocol config explicit assumption |
| `K_SCORE_GRID` | `system_model.py` | selector training | Validation grid | rounds | Training/validation only | Configured static | `(0,1,2,3,4,6)` | Runtime k-score | Training-only | Keep out of runtime config; legacy artifact provenance |
| `SEEN_SEQ_HORIZON` | `comms.py` | duplicate table | Sequence bookkeeping capacity | packets | Runtime | Module constant | `64` | none | module constant | Protocol config explicit structural limit |
| `PROGRESS_WINDOW_STEPS` | `comms.py` | own history/trigger | Local progress history | steps | Runtime | Module constant | `5` (`0.75 s`) | trigger hold count | Step literal | Controller/protocol seconds; derive steps |
| `LocalGains.k_*` | `local_controller.py` | local controller/signature | Eight fixed controller gains | unitless/group scales | Runtime | Constructor defaults | all `1.0` | centralized implicit weights | `LocalGains` | Immutable ControllerConfig; preserve all values |
| decentralized selector dimensions | `decentralized/models.py` constructors | model build/load | Ego hidden width/message passes | count | Runtime model artifact/training | Constructor defaults | `96`, `3` | legacy TrainConfig/model `128`, `3` | Constructor | ModelConfig; model family explicit |
| `FORWARD_SECTOR_FALLBACK_HALF_WIDTH` | `epoch.py` | fallback/diagnostic | N=6 widest role sector | m | Runtime fallback | Module literal | `1.45` | role derivation | Duplicate diagnostic | Remove active fallback; role information required |
| `L_TRIGGER` | `epoch.py` | scripts/tests compatibility | Evidence persistence | steps | Runtime compatibility | Module constant | `3` | derived persistence | Duplicate | Deprecated alias only, never active source |
| `PEER_SUPPORT_REQUIRED_FOR_ORIGINATION` | `epoch.py` | recovery arming | Whether peer support gates origin | boolean | Runtime | Explicit assumption | `False` | no equivalent | Module constant | Protocol config assumption |
| trigger clearance/progress/formation thresholds | `TriggerThresholds.from_config` | event trigger | Entry/recovery and diagnostics thresholds | m/steps | Runtime | Mixed derived | spacing/clearance, `2*spacing`, one-step distance, progress window, epsilon | Uses broad mutable env; recovery formula N=6-specific | Function | Preserve current behavior; move sources/derivations; topology redesign remains Phase 3/7 |
| `EPSILON_FORM` | `formation_metric_v3.py` | Metric V3/scripts | Frozen tube tolerance | m | Evaluation only | Module constant | `0.55` | env/mission | Metric constant | Compatibility alias to canonical derived tolerance; Metric V3 unchanged |
| `L_RECOVER` | `formation_metric_v3.py` and `reconfiguration_metrics.py` | metrics/scripts | Frozen recovery dwell | steps | Evaluation only | Two module constants | `20` | recovery seconds | Duplicate | Compatibility alias to canonical derivation |
| `RECOVERY_MARGIN` | `reconfiguration_metrics.py` | V2 metric | Downstream scoring margin | m | Evaluation only | Module constant | `0.5` | fixture safety margin differs | Metric module | EvaluationConfig only; Metric V3 remains authoritative current metric |
| fixture constants | `qualification_fixtures.py` | qualification only | IC tolerance, jitter, clearance, world/horizon/settling | mixed | Evaluation fixture | Module constants | `0.25,0.06,0.3,18,260,54` | Env defaults and manifests | Frozen fixture | Keep evaluation-only; never runtime defaults |
| layout geometry tables | `layouts.py`, `env_geometry.py` | data/evaluation | Scenario split geometry | m | Training/evaluation only | Module constants | family-specific tables | result manifests | Layout module | Preserve; not runtime configuration |

## 5. Constructor and function defaults that bypass configuration

| Default | Location | Effect | Classification | Required action |
|---|---|---|---|---|
| `CommParams()` fallback | runtime, ego graph, training, accounting, epoch | Recreates communication source independently at call sites | A: duplicated source | Resolve one immutable runtime config at boundary |
| `ConsensusParams()` fallback | runtime, ego graph, consensus, epoch, accounting | Recreates rounds/timing and preserves invalid `k_score=4` | A/C | Resolve and validate canonical protocol config |
| `Config()` fallback | parameters and qualification helpers | Pulls broad mutable training/evaluation object into default path | A/D | Compatibility adapter at simulation/offline boundary only |
| `LocalGains()` fallback | local controller | Hides controller values in constructor | A | ControllerConfig source |
| model `hidden_dim=96`, `passes=3` | decentralized model constructors/builder | Can bypass artifact/model configuration | A | ModelConfig or explicit checkpoint metadata |
| stale defaults `=3` | consensus/epoch simulation functions | Can disagree with communication period | A/C | Require derived stale rounds from config |
| `recovery_v2.rollout(h_commit=10)` | label generator | Independent step value | A | Training compatibility alias from physical commitment duration |
| metric function defaults bound to constants | Metric V3/reconfiguration metrics | Freeze copies at import time | A | Compatibility aliases derived once; new APIs accept explicit derived config |
| fixture `n=6`, script constants | qualification/experiment scripts | Experiment-specific scope | D | Keep evaluation only; never runtime default |

## 6. External configuration and serialization paths

| Parameter record | Current definition location | All use sites | Semantic meaning | Units | Runtime or evaluation only | Configured or derived | Current default | Duplicate definitions | Source of truth | Required action |
|---|---|---|---|---|---|---|---|---|---|---|
| run mode/device/results/workers | `run_experiments.py` CLI | experiment launcher | Execution controls | mixed | Training/evaluation | Configured | `train_all/auto/results/0` | TrainConfig | CLI override | Keep outside runtime manifest section |
| seed/episode/permutation CLI values | `run_experiments.py` | multi-seed evaluation | Experiment budget/provenance | mixed | Training/evaluation | Configured | optional, draws `5000` | Seed/Eval config | CLI override | Evaluation/training serialization |
| smoke CLI defaults | `scripts/scorefirst_smoke.py` | smoke only | Diagnostic budget | mixed | Training/evaluation | Configured | `30/20/32/...` | Train/Eval defaults | Script | Deprecated experiment profile; preserve reproducibility |
| binary pilot constants/CLI | `scripts/train_binary_pilot.py` | pilot training | Frozen pilot budget | mixed | Training/validation | Configured | epochs `24`, batch `32`, etc. | TrainConfig | Script | Preserve historical profile; not canonical RVT-FD runtime |
| ROS agent parameters | `agent_node.py`, `swarm_params.yaml` | legacy ROS centralized graph path | Robot IDs, topics, rate, radius, timeout, goal, twist conversion | mixed | Legacy runtime | Configured twice | rate `6.67 Hz`, radius `4.0 m`, timeout `1.0 s`, goal `(4,0)`, twist `2.8/0.22/1.82` | Python declarations and YAML; conflict with decentralized nominal values | ROS parameter server | Mark deprecated/non-RVT-FD; future production adapter phase, no Phase 2 behavior migration |
| ROS monitor parameters | `experiment_monitor.py` | Gazebo evaluation | timeout/rate/world/logging | mixed | Evaluation only | Configured | `90 s`, `6.67 Hz`, etc. | launch files | ROS parameter server | Evaluation config only |
| bridge YAML | ROS config files | Gazebo bridge | Topic type/direction | schema strings | Infrastructure | Configured | fixed topics | launch declarations | YAML | Out of numerical runtime contract |
| post-repair experiment manifest | `results/post_parameter_repair_regression/experiment_manifest.json` | frozen report scripts | Exact frozen sources/derivations/layout hashes | mixed | Evaluation record | Serialized record | schema-specific | values copied from old fragments | Immutable result | Do not rewrite or invalidate |
| other result JSON/YAML | `results/**` | reports/checkpoint provenance | Historical experiment records | mixed | Evaluation record | Serialized record | per experiment | may contain old names | Frozen artifacts | Never load as deployable config without migration |

## 7. Confirmed discrepancy classification

| Finding | Class | Evidence | Phase 2 disposition |
|---|---|---|---|
| Physical, sensing, formation, communication and timing values are copied across `EnvConfig`, parameter fragments and runtime params | A: duplicated source of truth | Tables 3 and 4 | Consolidate while preserving nominal values |
| `derived_max_message_age_steps` divides by control period, although freshness is counted in communication periods | C: confirmed correctness defect | Function implementation; defect is hidden when both periods are `0.15 s` | Correct derivation and add unequal-period tests |
| `ConsensusParams.k_score=4` is below default diameter bound `5` | C: confirmed contract defect | Approved Phase 2 requires all propagation/consensus round bounds at least diameter | Default to validated/derived diameter; document possible behavior effect |
| `ConsensusParams.for_protocol` is documented but absent | C: confirmed implementation defect | `system_model.py` comment and Phase 0 audit | Replace with actual canonical factory/derived view |
| Protocol default `max_team_size=6` blocks required mechanical sizes | B: unexplained fixed-size assumption | `ProtocolParams` default and support checks | Generic hierarchy and explicit per-run team/max size validation |
| Recovery trigger uses `2 * nominal_spacing` with N=6 template language | D: future architecture/topology gap | `TriggerThresholds.from_config` | Preserve current behavior; do not redesign trigger in Phase 2 |
| No readiness protocol exists although `k_ready` is required | D: future architecture gap | Phase 1 gap map | Define and validate config field only; no protocol implementation |
| ROS agent runs the legacy centralized policy path and has independent defaults | D: production adapter gap | `agent_node.py` imports top-level policy runtime | Declare deprecated; do not convert into RVT-FD runtime in Phase 2 |
| Metric V3 constants duplicate runtime mission values | A: duplicated source | `EPSILON_FORM`, `L_RECOVER` | Point compatibility constants to canonical derivations; metric formula unchanged |
| Fixture/layout/script constants are experiment-specific | D or evaluation-only explicit assumption | Frozen manifests and scripts | Keep isolated; do not promote to runtime defaults |

## 8. Inventory conclusion

The current parameter-semantics repair is sound groundwork but not yet one
authoritative contract. The consolidation must preserve the frozen nominal
physical values and role-dependent opening geometry while making these changes:

1. materialize one immutable runtime hierarchy before any robot-local call;
2. expose all step counts and round counts through one derived view;
3. use communication period for message-age conversion;
4. validate all propagation bounds, including future `k_ready` configuration;
5. keep training/evaluation config types out of runtime imports;
6. serialize only source values and verify, rather than trust, derived values;
7. retain old `Config`, result manifests, script profiles, and ROS parameters as
   explicit compatibility/deprecated paths where immediate deletion would harm
   reproducibility.

No code was changed before this inventory was completed.
