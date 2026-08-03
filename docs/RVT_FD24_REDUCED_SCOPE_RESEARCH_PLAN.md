# RVT-FD24 Reduced-Scope Research Plan

## Provisional Positioning

Provisional title:

**RVT-Swarm: Fully Decentralized Recoverability-Aware Reconfiguration Between
Compact and Line Formations for Variable-Size Robot Swarms**

Short alternative for the later novelty audit:

**RVT-Swarm: Leaderless Recoverability-Aware Compact/Line Reconfiguration**

Neither title is final. Quantitative manuscript results are not written in this
phase.

The planned contribution structure is limited to three points:

1. candidate-conditioned local recoverability prediction for COMPACT versus LINE;
2. leaderless distributed topology agreement and robot-local transition readiness;
3. variable-size decentralized evaluation through 24 robots.

Residual action is not a current contribution. It remains an optional
hypothesis and may be promoted only if a predeclared later comparison shows an
advantage over the frozen base controller.

## Frozen Research Object

The online candidate set is `(COMPACT, LINE)` and the graph is
`COMPACT <-> LINE` for every declared team size. The runtime starts in COMPACT,
except for explicitly declared and physically valid LINE narrow starts. KEEP is
a fixed baseline and historical negative result, not an online candidate.

The research problem still requires local ego-graph inference,
candidate-conditioned recoverability, peer score exchange, leaderless
agreement, robot-local readiness, synchronized confirmation, smooth transition
execution and robot-local control/safety projection.

## Next Permitted Phases

Future approved phases may define recoverability targets, dense residual-action
supervision, scenario splits, training orchestration and learned runtime
adapters. Before seed-0 they must freeze target semantics, loss definitions,
candidate batching, data provenance, seeds and acceptance gates.

They may not change topology geometry, controller or safety behavior,
transition profiles, protocol semantics, readiness, ego-graph schema, physical
configuration or Metric V3 because learning results are poor. No final-test
layout may be accessed during target design, training, validation or selection.
