# RVT-FD24 Robot-Local Model Architecture

## Authority and scope

`rvt-fd24-model/v1` is the authoritative architecture for future robot-local
inference over `rvt-ego-graph/v2`. Phase 5 defines and mechanically validates
the architecture. It does not train on scientific data and is not imported by
the active `_robot_decision` path.

Implementation lives only under `rvt_swarm.fd24`. Historical global models
remain under `rvt_swarm.models`; decentralized ego V1 selectors remain under
`rvt_swarm.decentralized.models` for current-runtime compatibility.

## Data flow

```text
35-wide node features + feature masks + node type
    -> one of 3 shared-type node projections

19-wide edge features + feature masks + edge type
    -> one of 4 shared-type edge projections

typed node and edge embeddings
    -> 3 local destination-grouped attention/message blocks
    -> SELF/root readout only

root representation
    + explicit topology embedding for IDs {KEEP=0, COMPACT=5, LINE=2}
    + observer-local candidate metadata and masks
    -> shared candidate fusion
    -> local recoverability logit head
    -> bounded residual-action head
```

There is one encoder, one candidate conditioner, and one pair of heads for all
robots and all candidates. Candidate ID is mapped by equality against the
declared vocabulary, not treated as a continuous ordinal and not used as a raw
linear scalar.

## Encoder

Node and edge inputs concatenate masked values with their Boolean feature masks.
This makes a measured zero distinguishable from missing data. Invalid padded
entities are not accepted as physical nodes; the Phase 4 representation omits
them. Variable-size batches are disjoint unions with no padding requirement.

Every message block computes messages from source hidden state, destination
hidden state, and typed edge embedding. Attention softmax is grouped by
destination node, so edges in another ego graph cannot affect its denominator.
Aggregation uses only declared edges. Layer normalization is applied per node
and never mixes nodes or graph samples.

The robot representation is `node_hidden[root_index]`. There is no mean, max,
add, attention, or token pooling across ego graphs or across a whole swarm.

## Candidate conditioning

The shared conditioner receives:

- an embedding selected from the explicit primary topology vocabulary;
- own candidate role offset;
- own displacement from committed to candidate role;
- own transition magnitude;
- own local transition observation extent;
- validity masks for those local values;
- candidate desired pairwise information already carried on observed local
  peer edges and encoded by the graph encoder.

It never receives a complete candidate template, global width/length, all-role
offset table, global formation error, or global feasibility outcome.

## Heads and outputs

The recoverability head emits one unrestricted scalar logit per
robot-candidate. `sigmoid(logit)` is exposed as local evidence probability. The
head does not compare candidates, select a topology, vote, or commit.

The residual head emits two raw components because the authoritative local
controller action contract is a planar acceleration vector. Its bounded output
is:

```text
residual = residual_limit * tanh(raw_residual)
```

Default SI limits are derived per component as 0.25 of the immutable maximum
acceleration, currently `(0.15, 0.15) m/s^2`. They are architecture
hyperparameters frozen before future training, not controller gain changes.

The optional `direct_local_action_ablation` is a separate head interface over
the same conditioned local embedding. It is not a member of the primary model
and is not active in runtime.

## Parameter structure

Default parameter counts are:

| Component | Parameters |
|---|---:|
| typed local encoder | 230,976 |
| candidate conditioner | 22,144 |
| recoverability head | 9,409 |
| residual-action head | 9,506 |
| total | 272,035 |

No parameter dimension contains N. Model output has shape `(ego_graph_count,
2)` for residual action, never `(team_size, 2)` from one ego graph.

## Design-choice classification

| Value | Classification | Rationale |
|---|---|---|
| 96 hidden units | pre-training model hyperparameter | reuses approved local V1 compute scale; not selected from Phase 5 outcomes |
| 3 message blocks | pre-training model hyperparameter | reuses approved local V1 depth |
| 16 candidate embedding units | standard design choice | lightweight relative to root width |
| ReLU | standard design choice | existing repository convention |
| per-node LayerNorm | locality constraint | avoids cross-graph batch statistics |
| dropout 0 | deterministic runtime constraint | exact batch/permutation isolation |
| float32 | runtime compute constraint | matches graph tensors and existing deployment |
| residual fraction 0.25 per dimension | frozen future-training hyperparameter | explicit bounded correction, not result-tuned |
