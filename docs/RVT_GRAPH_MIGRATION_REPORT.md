# RVT Graph Migration Report

## Disposition table

| Legacy graph path | Current usage | Local/global | New disposition | Runtime allowed | Checkpoint impact | Result impact | Deprecation status |
|---|---|---|---|---|---|---|---|
| `dataset.build_graph_arrays` / `build_graph` | historical training and policy preprocessing | global | delegated through `legacy_global_graph` for explicit compatibility | not in strict decentralized runtime | unchanged 68/11 checkpoints | none; files untouched | deprecated for new deployable work |
| `models.pooled_graph_features` | historical graph heads | global for historical inputs | retained with historical models | prohibited in strict namespace | unchanged | none | legacy only |
| `policy_runtime.batch_from_obs` | historical model runtime | global observation | imports `build_legacy_global_graph` explicitly | historical compatibility only | unchanged | none | named compatibility adapter |
| `decentralized.ego_graph.build_ego_graph` | active Phase 1 decentralized selector | local | frozen V1 compatibility path | yes until Phase 5 replacement is validated | unchanged 28/9 checkpoints | none | superseded for future heads, still active |
| `decentralized.training.batch_ego` | V1 offline batches | local samples | preserved for V1 | offline only | unchanged | none | legacy V1 training |
| ROS active-team graph recreation | historical ROS policy | local active set represented as one global-like graph | preserved, explicitly outside publication V2 | not strict V2 | unchanged | none | historical deployment compatibility |
| packaged ROS bundle | immutable historical copy | mixed | left untouched | historical artifact only | unchanged | none | frozen artifact |
| `decentralized.ego_graph_v2` | future model input | strictly local | authoritative V2 | yes as representation; no Phase 5 head active | requires new head reconstruction | none in Phase 4 | current authority |

## Runtime adapter

`RobotLocalEgoGraphRuntimeAdapter` binds one immutable `RuntimeConfig` and one
`RobotLocalTopologyMetadata` slice. Its only dynamic input is one current
`RobotView`, candidate topology ID, and local observation step. It changes no
controller action, score, topology proposal, or protocol state.

The active `_robot_decision` function still imports and calls V1
`build_ego_graph`. This is deliberate. A silent V2 switch would change tensor
semantics and current model outputs before Phase 5 method reconstruction.

## Semantic comparison

| Difference from V1 | Class | Disposition |
|---|---|---|
| schema/version/hash/masks/normalization | A: schema-only | adopted in V2 |
| COMPACT and general Phase 3 local topology slices | A: schema capability | adopted, not activated in control |
| canonical peer/obstacle ordering | A: representation | adopted in V2 |
| rejection of joint/mapping inputs and isolation from global builders | B: prohibited information removal | guarded; V1 active local path already complied |
| stale/invalid/lost peer omission and conflicting duplicate omission | C: invalid local data correction | V2 only; not silently applied to V1 model output |
| feature-mask treatment of missing velocity | C: missing-data correction | V2 only |
| controller/model/protocol output change | D: unintended regression | none observed; active path unchanged |

## Reproducibility impact

The compatibility wrapper delegates to the original global builder and is
bitwise-tested against it. No historical result file, checkpoint, topology,
controller, Metric V3 configuration, geometry, or physical configuration was
modified. V2 records cannot be interpreted by old checkpoints and old tensors
cannot be interpreted as V2 without rebuilding from original local inputs.
