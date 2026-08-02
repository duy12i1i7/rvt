# RVT Model Migration Report

## Classification policy

- A: directly compatible with FD24 V1.
- B: semantically identified tensors may be reused for initialization only.
- C: useful only as a diagnostic reference.
- D: historical and incompatible.

No inspected legacy checkpoint is class A. Phase 5 performs no weight import.

| Legacy asset | Old schema | New schema | Class | Reusable tensors | Rejected tensors | Semantic reason | Runtime status | Experiment impact |
|---|---|---|---|---|---|---|---|---|
| global `GraphBackbone` checkpoints | 68/11 whole-swarm | 35/19 local V2 | D | none loaded | all | input semantics, typed projections and edge widths differ | historical only | none |
| `RVTSwarmPolicy` | legacy global `[0,2,3]` | local `[0,5,2]` | D | none | encoder, topology, score, action, uncertainty, auxiliary | global pooling, ambiguous width-three vocabulary, full-action bank | historical only | none |
| `RVTSimpleRankPolicy` | global 68/11 | local V2 | D | none | all | pooled global context and full-node action bank | centralized diagnostic | none |
| `InstantCertPolicy` | global 68/11 | local V2 | D | none | all | pooled certificate is not robot-local evidence | historical only | none |
| `GNNOnlyPolicy` | global 68/11 | local V2 | D | none | all | action for every whole-swarm node, no candidate evidence | historical direct-action reference | none |
| binary recovery pilot | global 68/11 KEEP/LINE | local KEEP/COMPACT/LINE | D | none | all | no COMPACT, global pooled recovery, full action bank | historical diagnostic | none |
| direct KEEP/LINE classifier | global 68/11 | local V2 | D | none | all | direct winner and full actions, wrong vocabulary | ablation reference | none |
| decentralized V1 `EgoTrunk` | local 28/9 | local V2 35/19 | C | architecture idea only | all stored tensors | genuinely local but feature order, masks, typed encoders, edge width and conditioner differ | active current selector remains frozen | none |
| decentralized V1 recovery selector | local KEEP/LINE | local three-candidate | C | output semantics as design reference | checkpoint weights | lacks COMPACT, residual head and V2 contract | active V1 compatibility | none |
| ROS copied model bundle | copied global 68/11 | local V2 | D | none | all | active-set global-like preprocessing and copied pooling | immutable deployment artifact | none |

Some hidden-to-hidden tensor shapes happen to match dimensions used elsewhere.
That coincidence is not a locality or semantic proof. Random partial loading or
name-based slicing would falsely present initialization as faithful migration
and is prohibited.

Historical model factories, checkpoint readers, files, and results remain
unchanged. The new strict loader accepts only its own exact schema, so legacy
reproducibility is preserved without giving legacy assets a path into FD24.
