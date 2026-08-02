# RVT Configuration and Generality Contract

## 1. Authority and scope

The authoritative deployable configuration is
`rvt_swarm/runtime_configuration.py`, schema
`rvt-runtime-configuration/v1`, with derivations versioned as
`rvt-runtime-derivations/v1`.

This Phase 2 contract configures the selected KEEP/LINE base. It does not add
COMPACT, a topology registry, ego-graph V2, a residual action, transition
readiness, all-ready consensus, a safety projection, or a production adapter.
Configuration support at a team size is mechanical evidence only.

## 2. Immutable hierarchy

| Section | Ownership | Source quantities |
|---|---|---|
| `PhysicalPlatformConfig` | Deployable, shared static | Robot radius, motion bounds, control period |
| `MissionConfig` | Deployable, shared static | Team size, recovery dwell in seconds, frame and heading convention |
| `FormationConfig` | Deployable, shared static | Nominal spacing, tolerance ratio, spacing margin |
| `SensingConfig` | Deployable, shared static | `R_obs`, peer sensing envelope, lidar rays/FOV |
| `CommunicationConfig` | Deployable, shared static | Radio range/period, age/delay bounds, nominal link settings |
| `ProtocolConfig` | Deployable, shared static | Maximum team size, declared diameter, optional round bounds, physical lifecycle times, disconnection policy |
| `ControllerConfig` | Deployable, shared static | Frozen local-controller gains, progress window, declared transition envelope bounds |
| `SafetyConfig` | Deployable, shared static | Obstacle, inter-robot, and transition-observation margins |
| `ModelConfig` | Deployable, shared static | Preserved ego-selector dimensions, attention slope, input schema |
| `TrainingConfig` | Centralized training-only | Seeds, optimizer and training-budget values |
| `EvaluationConfig` | Centralized evaluation-only | Episode/world/metric settings |
| `ExperimentConfiguration` | Offline wrapper | One frozen runtime config plus separate training/evaluation sections |

Every dataclass in the hierarchy is frozen and hashable. Runtime modules import
only `rvt_swarm.runtime_configuration`; that module does not define or import a
training or evaluation config type.

Evaluation may wrap a runtime config but cannot mutate it. A changed source
requires construction of a new object with `dataclasses.replace`, producing a
different canonical hash.

## 3. Source and derived separation

Only source quantities appear as `RuntimeConfig` constructor fields. The
following are members of the immutable `DerivedRuntimeConfig` and cannot be
loaded or overridden independently:

- formation tolerance in meters;
- robot-obstacle and robot-robot required center clearances;
- minimum formation scale;
- recovery, commitment, evidence, rearm, decision-reference, and progress
  step counts;
- message stale and delay round counts;
- component and causal diameter bounds;
- `k_intent`, `k_score`, `k_ready`, and `k_confirm`;
- role-specific transition observation widths;
- sensor-observable maximum width;
- longitudinal lookahead distance.

`k_ready` is configured and validated now but is not executed by the selected
base. Phase 7 owns readiness implementation.

## 4. Validation contract

Construction performs basic type, unit-domain, and consistency checks. Full
mechanical validation is exposed by `assess_runtime_configuration` and enforced
by `require_supported_configuration` and derivation/serialization entry points.

Failure returns or raises structured `ConfigurationIssue` records containing:

```text
code | field_path | message
```

Validation rejects, without clamping or substitution:

- non-integer, nonpositive, or oversized team size;
- invalid physical periods, dimensions, probabilities, and margins;
- team size above `maximum_team_size`;
- invalid or impossible diameter assumptions;
- propagation rounds below the causal bound;
- unknown temporary-disconnection policy;
- spacing below required robot clearance;
- missing/incompatible persistent roles;
- non-disjoint current KEEP/LINE tubes;
- role transition width outside `R_obs`;
- invalid model dimensions or attention parameter;
- missing shared frame identity.

An unsupported result never silently changes team size, topology, spacing,
clearance, or sensor range.

## 5. Communication contract

The configuration distinguishes:

- `maximum_team_size`;
- `declared_maximum_component_diameter_hops`;
- communication period;
- maximum message delay and age in seconds;
- causal propagation and per-phase round bounds;
- temporary-disconnection behavior.

If no tighter diameter is declared:

```text
D_component = maximum_team_size - 1.
```

Message delay is converted to communication rounds. The implemented causal
bound is conservative:

```text
B_delay = ceil(maximum_message_delay_seconds / communication_period_seconds)
D_causal = D_component * (B_delay + 1)
```

Each configured/derived phase count must satisfy:

```text
k_intent, k_score, k_ready, k_confirm >= D_causal >= D_component.
```

The only supported temporary-disconnection policy is
`retain_current_topology_and_abort_epoch`. The selected base does not yet
implement generic readiness or the full abort policy; Phase 7/8 owns that gap.
No wider correctness claim is made here.

## 6. Variable-size mechanical contract

`RuntimeConfig.for_team_size(n, graph_family)` contains no N-specific branch.
Path, ring, star, and complete graph diameters are mechanically derived.

The frozen spacing, geometry, clearance, and `R_obs=3.0 m` mechanically support
the current KEEP/LINE construction for the required sizes:

| N | Path diameter | Maximum role observation half-width | Within `R_obs` | Scope |
|---:|---:|---:|---|---|
| 5 | 4 | about `1.45 m` | Yes | Configuration/mechanical only |
| 6 | 5 | about `1.45 m` | Yes | Configuration/mechanical; prior closed-loop evidence remains N=6 |
| 8 | 7 | about `1.45 m` | Yes | Configuration/mechanical only |
| 12 | 11 | about `1.90 m` | Yes | Configuration/mechanical only |
| 16 | 15 | about `1.90 m` | Yes | Configuration/mechanical only |
| 24 | 23 | about `2.35 m` | Yes | Configuration/mechanical only |

This does not establish learned inference, bandwidth, closed-loop passage, or
scientific success at N=24.

## 7. Deterministic serialization

`rvt_swarm/configuration_serialization.py` defines
`rvt-experiment-manifest/v1`.

Every manifest contains:

- experiment, runtime, and derivation schema versions;
- source commit;
- configurable runtime, training, and evaluation sections;
- explicit unit metadata;
- recalculated derived runtime values;
- canonical SHA-256 over runtime source values.

Canonical JSON uses sorted keys, compact separators, ASCII encoding, finite
numbers, and one trailing newline. Loading:

1. rejects unknown or missing fields;
2. rejects schema/version mismatch;
3. reconstructs frozen source dataclasses;
4. recalculates all derived values;
5. rejects a stale source hash or any tampered derived value;
6. never treats a serialized derived value as an override.

Semantically identical source configurations have the same canonical hash.
Source commit is manifest provenance and is intentionally not part of the
semantic runtime hash.

## 8. Compatibility boundary

The following remain for reproducibility but are deprecated as active RVT-FD
configuration sources:

- mutable `rvt_swarm.config.Config` and `EnvConfig`;
- flat `PlatformParams`, `MissionParams`, and `ProtocolParams`;
- `CommParams`, `ConsensusParams`, and `LocalGains` direct constructors;
- legacy centralized ROS 2 parameters and YAML;
- historical experiment-script constants and result manifests.

The simulator boundary may materialize one frozen `RuntimeConfig` from a legacy
environment object. From that point onward robot-local functions receive only
the frozen runtime hierarchy or a compatibility projection derived from it.
Historical result files are never loaded as deployable configuration.

## 9. Frozen semantics

Phase 2 preserves:

- robot radius `0.18 m`;
- robot-obstacle required center clearance `0.55 m`;
- robot-robot required center clearance `0.40 m`;
- `R_obs=3.0 m`;
- nominal spacing `0.9 m`;
- Metric V3 tolerance `0.55 m` and definition;
- recovery dwell `3.0 s` (`20` nominal control steps);
- all local-controller gains;
- current role-dependent opening geometry;
- corridor geometries, seeds, manifests, and the negative common-KEEP result.

No value was tuned against closed-loop success, and no scientific experiment
was run in Phase 2.

