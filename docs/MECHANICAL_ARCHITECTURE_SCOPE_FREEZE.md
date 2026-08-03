# Mechanical Architecture Scope Freeze

## Freeze Point

The mechanical scope is frozen from Phase 7R commit
`f74ba7d63e684be4213a89ca31d0214a48543b64`, tagged
`rvt-transition-execution-repair-v1`. Phase 7S adds publication admission and
candidate-scope configuration only; it does not repair mechanical behavior.

The frozen architecture comprises:

- immutable topology registry and persistent role construction;
- one publication graph, `COMPACT <-> LINE`;
- ego-graph schema and feature semantics;
- robot-local controller and action bounds;
- robot-local safety projection and safety clearances;
- generic smooth role-space transition profile;
- transition wire messages, flooding and lifecycle semantics;
- robot-local transition readiness, all-ready agreement and confirmation;
- physical and mission configuration;
- Metric V3 and formation tolerance.

No controller gain, topology geometry, local safety constraint, readiness rule,
protocol phase, message schema, transition duration derivation, physical
parameter or metric behavior may change before seed-0. Poor future learning
results are not authority to reopen this list.

## Scope Layer

`rvt_swarm.decentralized.online_topology_scope` filters publication requests
before the generic protocol. It admits only COMPACT/LINE edges, returns
structured rejection for KEEP or unknown edges and suppresses source-equals-
target lifecycle creation. `rvt_swarm.fd24.candidate_scope` similarly admits
only COMPACT and LINE to primary model batching and score agreement.

These layers do not alter generic historical replay, KEEP fixed-topology
execution or supported COMPACT/LINE mechanical outputs. Phase 7 and Phase 7R
result trees remain bitwise traceable through their source Git tree IDs.

## Future Work Boundary

This is not the final method freeze because scientific targets, datasets,
losses and trained checkpoints do not yet exist. Future approved work may add:

- recoverability-target generation;
- dense residual-action supervision;
- training orchestration and scenario splits;
- learned publication-runtime adapters.

Such work must consume the frozen candidate/transition contracts and preserve
the architecture above. Phase 7S generated no scientific label or action
dataset, trained no model and accessed no final-test layout.
