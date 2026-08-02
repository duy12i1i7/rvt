# RVT Legacy Model and Checkpoint Inventory

## 1. Scope and provenance

This inventory was completed before any Phase 5 model implementation change.
The approved source baseline is Phase 4 commit
`6f23ca180d964bf55750ba2e7397de13b3e4de3c`. It covers the source model
classes, model factories, active runtime loaders, offline training wrappers,
checkpoint writers and readers, checked-in checkpoint artifacts, decentralized
V1 selectors, the ROS deployment copy, graph pooling, candidate vocabulary,
action semantics, and feature dimensions.

Three incompatible learned-input contracts exist at the baseline:

- historical whole-swarm graph: 68 node features and 11 edge features;
- decentralized ego graph V1: 28 node features and 9 edge features;
- authoritative future ego graph V2: 35 node features and 19 edge features.

No historical checkpoint declares `rvt-ego-graph/v2` or feature hash
`1ea52c6aebb23360641ce6a09ef41d2d21fd372f2744f196b91ff184a1a2cf5b`.

## 2. Model inventory

| Model or class | Source file | Input graph schema | Local or global | Pooling | Candidate conditioning | Output heads | Action semantics | Variable-N support | Checkpoint schema | Runtime use | Recommended disposition |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `GraphBackbone` / `GraphLayer` | `rvt_swarm/models.py` | historical 68/11 | global because preprocessing builds a whole-swarm graph | none inside backbone | none | node embeddings | none directly | tensor-mechanical yes | inherited from wrappers | historical wrappers | centralized historical encoder only |
| `GNNOnlyPolicy` | `rvt_swarm/models.py` | historical 68/11 | global | none for action | none | per-node action | full normalized action for every graph node, shape N x 2 | mechanical yes; output scales with N | legacy training checkpoint | historical learned runtime | direct full-action historical ablation only |
| `InstantCertPolicy` | `rvt_swarm/models.py` | historical 68/11 | global | whole-graph mean for certificate | none | per-node full action and pooled certificate | full normalized action for every node | mechanical yes | legacy training checkpoint | historical learned runtime | centralized diagnostic only |
| `RVTSwarmPolicy` | `rvt_swarm/models.py` | historical 68/11 | global | whole-graph mean plus pooled topology consensus | legacy one-hot bank | base action, topology delta, topology classifier, recoverability/ranking, uncertainty, auxiliary | full action bank for every node and legacy candidate | mechanical yes | legacy training checkpoint | historical learned runtime | historical and incompatible |
| `RVTSimpleRankPolicy` | `rvt_swarm/models.py` | historical 68/11 | global | whole-graph means | legacy one-hot bank | ranking score and action bank | full action for every node/candidate | mechanical yes | legacy training checkpoint | historical learned runtime | centralized diagnostic only |
| `DirectTopologyClassifierPolicy` | `rvt_swarm/models.py` | historical 68/11 | global | inherited whole-graph pooling | legacy one-hot bank | hard topology classifier and action bank | full action for every node/candidate | mechanical yes | legacy training checkpoint | historical baseline | explicit classifier ablation only |
| `RVTBinaryRecoveryPolicy` | `rvt_swarm/models.py` | historical 68/11 | global | whole-graph mean | binary KEEP/LINE one-hot | two recovery logits and two action heads | full action bank for every node, shape N x 2 x 2 | mechanical yes | pilot selected checkpoint | historical learned runtime | historical recovery diagnostic only |
| `DirectKeepLineClassifier` | `rvt_swarm/models.py` | historical 68/11 | global | inherited whole-graph mean | binary KEEP/LINE one-hot | softmax classifier and action bank | full action bank for every node | mechanical yes | pilot selected checkpoint | historical baseline | direct classifier ablation only |
| `EgoTrunk` / `EgoLayer` | `rvt_swarm/decentralized/models.py` | decentralized ego V1 28/9 | robot-local | root-node readout, no graph pool | candidate encoded in V1 graph | one root embedding | none | yes | selector result artifact | active decentralized selector | freeze for current runtime compatibility |
| `DecentralizedRecoverySelector` | `rvt_swarm/decentralized/models.py` | decentralized ego V1 28/9 | robot-local | root-node readout | same weights applied separately to KEEP and LINE V1 graphs | one scalar logit per robot-candidate | no action head | yes | ad hoc selector result artifact | active optional selector through `_robot_decision` | preserve until a later authorized activation phase |
| `DecentralizedDirectSelector` | `rvt_swarm/decentralized/models.py` | decentralized ego V1 28/9 | robot-local | root-node readout | same weights applied separately to KEEP and LINE | one direct-choice scalar per robot-candidate | no action head | yes | ad hoc selector result artifact | active optional selector | historical V1 local ablation |
| copied global policy classes | `deploy/rvt_swarm_ros2_jazzy_bundle/rvt_swarm/models.py` | copied historical 68/11 | global-like active peer set | whole-graph pooling | legacy | copied action/topology/recovery heads | actions for every active node before self extraction | yes for active-set size | copied legacy format | packaged historical ROS deployment | immutable historical bundle |
| `fixed_keep_policy` | factory/baseline path | none | N/A | none | fixed KEEP | no learned head | verified scripted controller | yes | none | non-learned baseline | preserve as non-learned reference |

There are no GRU, LSTM, RNN, or other recurrent components in the discovered
model paths. There is no fixed-N linear layer, but the historical full-action
heads emit one action for every node in a complete-swarm graph, so their output
semantics are joint even though parameter shapes do not contain N.

## 3. Preprocessing and apparent locality

`policy_runtime.batch_from_obs` consumes the complete observation dictionary
through `legacy_global_graph`. Its model input includes whole-swarm and global
preprocessing documented in the Phase 4 graph inventory. The ROS adapter uses
only its active local peer set but reconstructs that set as one whole graph,
computes active-set centroid/statistics, runs a historical global model for all
nodes, and then selects self. It is not an authoritative robot-local V2 path.

The decentralized V1 selectors are genuinely local, but they cannot consume
V2: their input layers require 28/9, their candidate vocabulary is binary, they
have no residual-action head, and their tensors lack V2 masks and hashes.

## 4. Candidate and topology conditioning

Historical global structural heads use `LEARNED_TOPOLOGY_IDS = [0, 2, 3]`,
meaning KEEP, LINE, and legacy `split_hint`. The authoritative Phase 3/4
vocabulary is `[KEEP=0, COMPACT=5, LINE=2]`. Therefore a width-three historical
head is not position-compatible with the new vocabulary.

Binary pilot and decentralized V1 heads use KEEP/LINE only. Candidate inputs
are one-hot vectors or are embedded directly in V1 graph features. No baseline
model has a reusable authoritative COMPACT embedding. No independent recurrent
or per-topology encoder exists; historical action banks share a backbone but
their vocabulary semantics are incompatible.

## 5. Checkpoint inventory

| Checkpoint family | Artifacts inspected | Metadata observed | Graph/schema declaration | Vocabulary declaration | State shape evidence | Runtime reader | Disposition |
|---|---|---|---|---|---|---|---|
| method-audit and smoke protocol | `checkpoints/method_audit/*.pt`, `checkpoints/smoke_protocol_v2/*.pt` | model, optional optimizer/config, epoch, metric, evaluation schema, git commit | none; first node layer is 128 x 68 and edge layer is 128 x 267 | inferred from model name only | 35 tensors for `gnn_only`, 67 for `rvt_swarm` | `policy_runtime.load_learned_model` and scripts | historical global only |
| binary pilot dry run | three `selected.pt` artifacts | method, source commit, data/evaluation tags, writer token, budget and validation summaries | none; first node layer is 128 x 68 | inferred binary method only | 35 or 47 tensors | pilot scripts | historical diagnostic only |
| decentralized selector | `results/*_seed0.pt` when generated | model, selected `k_score`, parameter count and provenance stamp | no explicit V1 graph schema/hash | inferred binary method only | V1 28/9 model state | evaluation scripts | preserve, not V2-compatible |
| ordinary training writer | `rvt_swarm/train.py` | model, optional optimizer/config, epoch, metrics, model name, evaluation schema, git commit | none | model-name inference | state dict only | training resume and policy runtime | deprecated for new FD24 checkpoints |
| pilot writer | `scripts/train_binary_pilot.py` | selected state, method, provenance, budget, scientific metrics | none | method inference | state dict only | pilot evaluation | do not extend for FD24 |

No inspected checkpoint contains a model-config hash, runtime-config hash,
explicit action dimension, exact residual bounds, V2 feature hash, state-dict
content hash, local/global information-scope declaration, or unambiguous primary
topology vocabulary.

## 6. Explicit risk findings

- Whole-swarm encoders and pooling are active in historical global model paths.
- `pooled_graph_features` implements global mean pooling for historical inputs.
- Historical models emit N x action-dimension tensors or N x candidate x
  action-dimension banks from one whole-swarm graph.
- No fixed-N linear layer was found; joint action semantics arise from per-node
  output over a global graph instead.
- Historical direct-action heads predict complete actions, not bounded
  corrections to a verified base controller.
- Action heads were trained in old protocols, including sparse recovery-state
  paths and later dense historical action datasets; none has V2 semantics.
- Width-three topology heads are ambiguous and semantically conflict with
  COMPACT ID 5.
- Tensor width, matching hidden dimension, or matching action dimension is not
  sufficient checkpoint provenance.
- The ROS copy and root historical models must remain reproducible but isolated
  from a strict FD24 model namespace.

## 7. Inventory gate

The inventory covers every learned class, shared encoder, graph pool, action
head, recoverability/certificate head, topology classifier, model factory,
training wrapper, active runtime loader, checkpoint writer/reader, checked-in
checkpoint family, and deployment copy found at the approved Phase 4 baseline.
Phase 5 implementation may now begin.
