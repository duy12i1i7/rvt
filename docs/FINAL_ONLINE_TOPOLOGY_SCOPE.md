# Final Online Topology Scope

## Authority

Phase 7S freezes the publication runtime at Phase 7R commit
`f74ba7d63e684be4213a89ca31d0214a48543b64`, tagged
`rvt-transition-execution-repair-v1`. The machine-readable authority is
`results/rvt_fd24/online_topology_scope.json`, schema
`rvt-online-topology-scope/v1`. Its canonical SHA-256 is
`bc65ec533c895a9ad82ef277e89998c772db3403d4177ec04d9dce375f0c7684`.

The online candidate order is explicit and does not depend on registry
iteration:

| topology | ID | publication role |
|---|---:|---|
| COMPACT | 5 | moderate-footprint operational formation for open and moderately constrained environments |
| LINE | 2 | narrow elongated formation for restricted passages |
| KEEP | 0 | fixed baseline, qualification, diagnostic and historical use only |

COMPACT is not a rename of KEEP. Their registry geometry, nominal graph and
operational semantics remain distinct.

## Frozen Graph

The one authoritative directed graph is:

`COMPACT -> LINE`

`LINE -> COMPACT`

It applies without per-cell selection to `N in {5, 6, 8, 12, 16, 24}`. Both
directions passed every declared Phase 7R team-size cell. The graph does not
vary by team size, scenario, seed or communication fixture.

The publication runtime rejects these edges with a structured
`UNSUPPORTED_TRANSITION` result and creates no lifecycle:

- `KEEP -> COMPACT`
- `COMPACT -> KEEP`
- `KEEP -> LINE`
- `LINE -> KEEP`

No rejected edge is routed through an intermediate topology. A source equal to
its target returns `NO_TRANSITION_REQUIRED` before intent creation and therefore
creates no epoch. An unregistered ID returns `UNKNOWN_TOPOLOGY`.

## Compatibility Boundary

The generic `rvt-transition-protocol/v1` messages continue to represent all
registered, unequal topology pairs. Historical and diagnostic replay can
deserialize KEEP records and classifies them as `HISTORICAL_REPLAY_ONLY`; this
does not authorize a publication transition.

KEEP remains in the topology registry, controller tests, Metric V3, forced
topology runtime, historical manifests and baseline evaluation. It cannot be a
publication online source, target, learned candidate or required recovery
topology.

The primary problem is now repeatable decentralized reconfiguration from
COMPACT to LINE under constrained recoverability evidence and from LINE to
COMPACT after robot-local readiness and leaderless agreement establish that
wider operation is feasible.
