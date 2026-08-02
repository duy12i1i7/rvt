# Phase 4 Ego Graph Report

## Scope and provenance

Approved base: `c44389900276d4c98b6c0f4503dbef53218962aa` on
`research/rvt-swarm-fd24-v1`. Phase 4 implemented only the robot-local ego graph
V2 and its runtime information boundary.

No topology geometry, topology ID, persistent role semantics, nominal
neighbour graph, controller gain, Metric V3 definition, formation tolerance,
physical configuration, communication assumption, checkpoint, or historical
result file changed. No scientific closed-loop experiment was run and no
final-test layout was accessed.

## Delivered implementation

- Authoritative schema `rvt-ego-graph/v2`, feature width 35/19, normalization
  `rvt-ego-normalization/v1`, and canonical serialization.
- One SELF root, fresh one-hop PEER nodes, locally sensed OBSTACLE nodes, four
  directed root-incident edge types, and per-feature validity masks.
- KEEP, COMPACT, and LINE conditioning through an observer-only topology slice
  produced at static mission setup.
- Canonical duplicate/freshness handling, coordinate conversion, physical
  normalization, variable-size disjoint batching, hashing, and strict loading.
- `RobotLocalEgoGraphRuntimeAdapter` from current `RobotView`; the active V1
  selector and all decisions remain unchanged.
- Historical 68/11 global graph isolated as `legacy_global_graph`; compatibility
  is bitwise-tested and prohibited from the strict decentralized namespace.
- Ten required documents and twelve required test files.

The feature registry includes 22 node blocks and 9 edge blocks. It rejects 16
documented global, future, evaluation-only, map-shortcut, transitive, and
dataset-statistic features. Exact semantics and rejection reasons are in
`RVT_EGO_GRAPH_FEATURE_REGISTRY.md`.

## Verification

The approved Phase 3 suite collected 1004 tests. Phase 4 collects 1202, adding
198 tests. The working-tree full run completed with `1202 passed, 1 warning` in
59.14 seconds. The warning is the pre-existing PyTorch scalar-conversion warning
in `tests/test_simplified_model.py`.

Targeted Phase 4 plus strict and magic-number guards collected 223 tests and
completed without failure. Direct guard results were:

| Audit | Result |
|---|---:|
| strict decentralization violations | 0 |
| global graph/pooling path violations | 0 |
| unexplained runtime constants | 0 |
| required intervention cases | 10/10 invariant |
| positive local peer/obstacle interventions | changed intended rows |
| candidate displacement intervention | changed only declared root candidate blocks |
| variable N | 5, 6, 8, 12, 16, 24 pass |
| topology candidates | KEEP, COMPACT, LINE pass |
| degree cases | zero, one, path, ring, bounded, complete diagnostic pass |
| obstacle cases | zero, one, multiple, out-of-range, stale, partial pass |

Interventions changed out-of-range robot position and velocity, unobserved
obstacle, global centroid, global formation error, unobserved role, unobserved
topology state, passage label, final outcome, and simulator obstacle ordering.
With all permitted local inputs fixed, graph fingerprints remained exact.

## Acceptance gates

| Gate | Result | Evidence |
|---|---|---|
| P4-G1 authoritative schema | pass | one versioned future schema and feature hash |
| P4-G2 strict locality | pass | exact local builder signature and zero strict violations |
| P4-G3 intervention invariance | pass | all ten negative and three positive interventions |
| P4-G4 variable size | pass | all required N plus mixed-N batch |
| P4-G5 variable degree | pass | zero through complete N=24 diagnostic |
| P4-G6 topology support | pass | all primary IDs from Phase 3 registry |
| P4-G7 freshness | pass | stale/lost/invalid omitted; duplicate policy tested |
| P4-G8 ordering | pass | peer, obstacle, robot, registry, batch permutations |
| P4-G9 no global pooling | pass | static guard 0; no cross-graph edge |
| P4-G10 scaling | pass | N=24 sparse and dense construction completed |
| P4-G11 legacy reproducibility | pass | explicit wrapper is bitwise-compatible |
| P4-G12 scope control | pass | no learned head, training, protocol, safety, or experiment added |

## Scaling summary

Detailed results are in `PHASE4_EGO_GRAPH_SCALING_REPORT.md`. With 1.5 local
obstacles per robot, N=24 ring graphs average 2 peers, 7 edges, 1,668 tensor
bytes, and 3.9584 ms/robot. N=24 bounded-degree graphs average 4 peers, 11 edges,
2,516 bytes, and 6.9510 ms/robot. The complete stress case reaches 23 peers,
49 edges, 10,572 bytes, and 35.4728 ms/robot. This confirms mechanical scaling
without claiming scientific validity at N=24.

## Runtime and result impact

Runtime adapter status: implemented but not activated by `_robot_decision`.
Legacy migration status: explicit compatibility namespace; unsafe width-only
migration rejected. Behavior-affecting changes: none. Historical checkpoint
impact: none. Historical result impact: none.

COMPACT remains mechanically represented but not closed-loop qualified. Phase
5 still needs model-head reconstruction for 35/19 tensors, training and method
validation under its own approved scope. Real transport adapters also still
need an explicit policy for non-integer robot keys and richer obstacle
age/confidence instead of historical tuple defaults.

## Verdict

C. The authoritative robot-local ego graph is valid; proceed to Phase 5.
