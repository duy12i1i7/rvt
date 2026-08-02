# RVT-FD24 Model Schema

## Version identifiers

| Contract | Identifier |
|---|---|
| model | `rvt-fd24-model/v1` |
| model configuration | `rvt-fd24-model-config/v1` |
| model input wrapper | `rvt-fd24-model-input/v1` |
| model output | `rvt-fd24-model-output/v1` |
| checkpoint | `rvt-fd24-checkpoint/v1` |
| accepted ego graph | `rvt-ego-graph/v2` |
| accepted feature hash | `1ea52c6aebb23360641ce6a09ef41d2d21fd372f2744f196b91ff184a1a2cf5b` |
| topology registry | `rvt-topology-registry/v1` |

## Input contract

`FD24LocalModelBatch` wraps one canonical disjoint batch of independently valid
`RobotLocalEgoGraph` records. It records graph, feature, and topology schemas;
per-graph runtime-configuration hashes; and per-graph fingerprints.

The tensor contract requires:

- node width 35 and edge width 19;
- explicit Boolean node and edge feature-validity masks;
- one SELF root per graph;
- only valid, finite, non-padded physical nodes and edges;
- no cross-ego-graph edge;
- candidate ID in `{0, 5, 2}` with explicit names KEEP, COMPACT, LINE;
- canonical graph-to-input mapping retained after batching.

The model rejects dictionaries, raw 68/11 or 28/9 tensors, missing masks,
unknown schemas, changed feature hash, unknown candidate IDs, malformed roots,
cross-graph edges, and non-finite values. It never pads, truncates, reshapes, or
reinterprets incompatible features.

## Candidate contract

Candidate identity uses the exact vocabulary:

```text
[(0, "KEEP"), (5, "COMPACT"), (2, "LINE")]
```

The non-contiguous IDs are compared against this table before embedding. A
legacy width-three head over `[0, 2, 3]` is incompatible even though its tensor
width is also three.

## Output contract

`RVTLocalBatchOutput` contains aligned vectors/tensors for:

- observer robot ID;
- candidate topology ID;
- one recoverability logit;
- one sigmoid local evidence probability;
- one bounded two-component residual action;
- one validity flag;
- canonical-to-input graph mapping;
- graph fingerprint;
- optional conditioned embedding only when both model and caller explicitly
  enable diagnostics.

`RVTLocalCandidateOutput` is the immutable one-sample projection. It preserves
observer, candidate, and graph identity. No selected topology, swarm vote,
joint action, lifecycle change, or controller command is present.

Numerical precision is float32. IDs are int64, masks are Boolean, and all
public numeric outputs must be finite. Residual action dimension is derived
from the named planar controller action components, not from N.

## Batching semantics

Central batching is permitted for tests and future offline training only. Every
edge remains inside one graph, attention normalization is destination-local,
normalization is per node, and output rows map to graph roots. Adding or
reordering unrelated graphs cannot change an existing local output.

## Compatibility policy

Only the exact model/config/graph/topology/checkpoint contracts above are
compatible. Legacy checkpoint tensor widths do not establish compatibility.
Migration requires an explicit semantic report; silent partial state loading is
prohibited.
