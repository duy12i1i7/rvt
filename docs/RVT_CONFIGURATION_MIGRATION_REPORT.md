# RVT Configuration Migration Report

## 1. Migration scope

Phase 2 consolidates deployable source values and derivations without adding a
later-phase architecture. The detailed pre-change inventory is
`docs/RVT_EXISTING_CONFIGURATION_INVENTORY.md`.

## 2. Source migration

| Old source | New authoritative source | Semantic equivalence | Migration method | Affected modules | Behavior change | Tests | Result invalidation status |
|---|---|---|---|---|---|---|---|
| Mutable `EnvConfig` physical fields | `PhysicalPlatformConfig` | Same nominal radius, motion bounds and control period | Simulator boundary materializes frozen runtime config | runtime, local controller, epoch, parameter facade | None nominal | configuration, derivation, existing controller/runtime tests | Existing manifests remain source-commit valid |
| `EnvConfig.nominal_spacing`, tolerance and spacing margin | `FormationConfig` plus derivation | Same `0.9 m`, `0.55 m`, `0.05 m` | Tolerance stored as ratio and derived in meters | roles, controller, trigger, Metric V3 compatibility constants | None nominal; Metric V3 formula unchanged | contract, Metric V3, parameter scaling | None |
| `EnvConfig` lidar/sensing values and `CommParams.r_obs/r_sense` | `SensingConfig` | Same `R_obs=3.0 m`, peer envelope `4.0 m`, lidar shape | Compatibility projections source from frozen config | comms, ego graph, parameter facade | None | ego locality, configuration scaling | None |
| `PlatformParams.communication_range=3.0` literal and `CommParams.r_comm` | `CommunicationConfig.communication_range_meters` | Same nominal `3.0 m` | Flat class becomes compatibility projection | comms/radio/runtime/manifests | None | neighbour discovery, config tests | None |
| `EnvConfig.dt`, `CommParams.t_ctrl/t_comm`, platform periods | Physical control period and communication period | Same nominal periods; clocks now distinct sources | One derived view converts each semantic on its own clock | comms, epoch, metrics, runtime | Corrected only when periods differ | time-domain and communication-period tests | Historical equal-period results unchanged |
| `ProtocolParams.max_message_age_seconds` plus step literals | `CommunicationConfig.maximum_message_age_seconds` -> `message_stale_rounds` | Same nominal `0.45 s -> 3` | Derive with communication period | comms, consensus, ego graph, epoch | Correctness fix for unequal periods | derived semantics, existing freshness tests | No frozen equal-period result invalidated |
| `ProtocolParams` lifecycle seconds plus `h_commit/L_TRIGGER/L_RECOVER/25/5` step copies | `MissionConfig`, `ProtocolConfig`, `ControllerConfig` -> `DerivedRuntimeConfig` | Same nominal physical durations | Step constants removed as active sources; compatibility aliases derive from sources | epoch, comms, metrics, scripts | None nominal | control-frequency invariance, lifecycle tests | None |
| `ProtocolParams.max_team_size=6` default | `ProtocolConfig.maximum_team_size=24` plus explicit run `team_size` and declared diameter | Generic maximum; default mission remains explicit N=6 | Factory derives per-run diameter without N branch | validation, compatibility facade | No default N=6 geometry change | N=5/6/8/12/16/24 mechanical tests | No scientific claim/result change |
| `ConsensusParams.k_trigger/k_confirm=5` and absent `for_protocol` | Derived `k_intent/k_confirm` and actual factory | Same nominal values | Compatibility view materialized from runtime config | epoch/runtime/system model | None | path/ring/star/complete propagation/config tests | None |
| `ConsensusParams.k_score=4` | Derived/validated `k_score>=D_causal` | Not equivalent; old value under-covered declared diameter 5 | Confirmed correctness repair | consensus runtime and message accounting | **Yes: nominal score rounds `4 -> 5`** | communication accounting updated to source live value; full protocol suite | Existing old results remain valid only for their old source commits; no file rewritten |
| Missing readiness round config | `ProtocolConfig.readiness_rounds` -> `k_ready` | New configuration-only contract | Derived and validated, not executed | configuration only | No runtime behavior | config/diameter tests | None |
| `LocalGains` constructor literals | `ControllerConfig` | All eight gains remain `1.0` | Compatibility view from runtime config | local controller | None | controller and configuration tests | None |
| Decentralized model constructor `96/3` and attention `0.2` | `ModelConfig` | Same architecture | Constructor defaults reference shared static source | decentralized models | None | existing model tests, config isolation | Existing checkpoints remain shape-compatible |
| `EPSILON_FORM=0.55`, duplicate `L_RECOVER=20` | Formation/recovery derivations | Same values and Metric V3 behavior | Offline compatibility constants reference canonical sources | formation/reconfiguration metrics and scripts | None | Metric V3/full suite | None |
| N=6 forward-sector fallback `1.45` | Role-specific transition-observation derivation | Runtime already used role data; unused fallback duplicated outer width | Removed fallback constant | epoch | None | role-width and existing detector tests | Negative common-KEEP result preserved |
| Independent `default_parameters()` bundle | `RuntimeConfig` plus deprecated projection facade | Same nominal flat values | Facade projects one frozen config | epoch/runtime/scripts/tests | Active runtime no longer uses it | old parameter tests plus new contract tests | None |
| Ad hoc post-repair manifest builder | Versioned canonical serializer | Same requirement to expose source/derived values, generalized | Strict deterministic JSON, hash, round-trip and tamper checks | new offline serialization module | No runtime behavior | serialization suite | Existing manifest is not migrated or overwritten |
| ROS Python/YAML defaults | No RVT-FD migration in Phase 2 | Legacy centralized production prototype remains distinct | Explicit deprecation only | ROS 2 package | None | isolation/source audit | No ROS result relabeled |

## 3. Removed constants and active duplicates

Removed as active sources:

- `FORWARD_SECTOR_FALLBACK_HALF_WIDTH=1.45`;
- hard-coded stale-round defaults in consensus/epoch simulation helpers;
- independent decentralized model defaults `96`, `3`, and attention `0.2`;
- duplicate Metric V3/reconfiguration recovery step source;
- controller gain literals as active constructor authority;
- broad mutable `Config` access inside robot-local controller/epoch/runtime
  functions.

Compatibility names `L_TRIGGER`, `EPSILON_FORM`, `L_RECOVER`, `CommParams`,
`ConsensusParams`, `LocalGains`, and flat parameter records remain derived
views. They are not independently serialized deployable sources.

## 4. Explicit assumptions retained

The following remain configured rather than derived:

- communication range, delay/loss/symmetry assumptions;
- maximum team size and optional tighter diameter;
- physical lifecycle durations and minimum confirmation margin;
- duplicate sequence horizon and temporary-disconnection policy;
- shared frame/heading convention;
- controller gains and transition response/drift bounds;
- model shape/schema.

Fixture geometry, corridor coordinates, seeds, training budgets, validation
grids, and evaluation margins remain evaluation-only assumptions.

## 5. Deprecated compatibility paths

The following are retained to avoid destroying reproducibility:

1. mutable `rvt_swarm.config.Config/EnvConfig` for the legacy simulator,
   training code and old checkpoints;
2. `decentralized.parameters` flat facade;
3. direct `CommParams`, `ConsensusParams`, and `LocalGains` construction in
   historical tests/diagnostics;
4. legacy script CLI defaults and frozen result manifests;
5. the centralized ROS 2 agent parameter/YAML path.

New RVT-FD deployable code must not add a dependency on these paths.

## 6. Behavior and result validity

Behavior-affecting corrections are limited to:

- nominal score consensus now uses 5 rounds instead of 4 because all protocol
  phases must cover the declared N=6 path diameter;
- message stale rounds now use communication period, which differs only when
  control and communication periods differ.

No closed-loop experiment was run, so no result was tuned or regenerated.
Existing result artifacts remain valid records of their exact historical
commits and manifests. They are not valid Phase 2 outputs and must not be
silently overwritten or pooled with a future post-Phase-2 rerun. No existing
result file is invalidated or modified by this migration.

The frozen negative common-KEEP regression remains unresolved and unchanged.

## 7. Acceptance gates

| Gate | Status | Evidence |
|---|---|---|
| P2-G1 authoritative configuration | Pass | One immutable runtime hierarchy; old records are explicit projections/deprecations |
| P2-G2 immutability | Pass | Frozen nested dataclasses and immutable reload tests |
| P2-G3 derivation consistency | Pass | One `DerivedRuntimeConfig`, formula and sensitivity tests |
| P2-G4 no magic numbers | Pass | Extended guard plus five required mutation categories |
| P2-G5 runtime isolation | Pass | AST import tests and strict decentralization audit |
| P2-G6 variable size | Pass mechanically | N=5/6/8/12/16/24 and explicit unsupported results |
| P2-G7 communication correctness | Pass for configuration | Diameter/delay validation and graph-family tests; readiness execution remains Phase 7 |
| P2-G8 time consistency | Pass | Two control frequencies and two communication periods |
| P2-G9 reproducibility | Pass | Deterministic JSON, canonical hash, round-trip and tamper rejection |
| P2-G10 scope control | Pass | No Phase 3+ architecture or scientific experiment |

## 8. Phase 3 blockers

There is no configuration blocker to begin Phase 3. Phase 3 must consume the
immutable topology/role-relevant sections and preserve structured unsupported
results. Remaining architecture gaps are intentional: no generic topology
registry, COMPACT role coordinates, readiness implementation, residual action,
safety projection, or production adapter exists yet.

## 9. Verdict

**C. Configuration and derivation contracts are valid; proceed to Phase 3.**

