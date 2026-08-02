# RVT-FD24 Model Checkpoint Contract

## Schema

New checkpoints use `rvt-fd24-checkpoint/v1`. The record is closed: missing or
unknown fields are rejected. Required fields are:

| Field | Required value or semantics |
|---|---|
| checkpoint schema | exact FD24 checkpoint version |
| model schema | `rvt-fd24-model/v1` |
| ego graph schema | `rvt-ego-graph/v2` |
| ego feature hash | exact Phase 4 SHA-256 |
| topology registry | `rvt-topology-registry/v1` |
| topology vocabulary | explicit ID/name records for KEEP 0, COMPACT 5, LINE 2 |
| model configuration | complete canonical typed source |
| model-config hash | SHA-256 of canonical config JSON |
| runtime-config hash | SHA-256 of immutable runtime source values |
| action dimension | exact derived local action dimension |
| residual bounds | exact SI value for every action component |
| source commit | 40-character lowercase Git SHA-1 |
| state-dict hash | SHA-256 over sorted name, dtype, shape, and tensor bytes |
| training status | `untrained`, `synthetic-mechanical`, or future explicit `scientifically-trained` |
| deployment classification | `shadow-disabled`, `diagnostic-only`, or future `deployable-candidate` |
| information scope | exact `robot-local-ego-v2` |
| state dict | complete strict model state |

Phase 5 checkpoints are untrained and `shadow-disabled`. The schema permits a
future scientifically trained status but Phase 5 does not create such an
artifact.

## Loading and rejection

The loader uses restricted tensor loading, validates the closed metadata before
model construction, rebuilds the typed configuration, verifies config and
runtime hashes, checks topology vocabulary and residual limits, hashes tensor
content, constructs the exact architecture, and calls strict state-dict load.

It rejects:

- unknown graph/model/checkpoint/config/topology schema;
- changed feature hash;
- vocabulary `[0,2,3]` or any ambiguous IDs;
- incompatible or N-dependent action width;
- missing metadata or extra legacy provenance fields;
- global information-scope declaration;
- changed runtime or model configuration;
- changed residual bounds;
- state tensor tampering or incompatible shapes;
- a historical global checkpoint presented as FD24.

There is no silent reshape, truncation, default vocabulary, or `strict=False`
loading. Matching tensor width alone never establishes compatibility.
