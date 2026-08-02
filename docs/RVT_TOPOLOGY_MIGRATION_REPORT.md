# RVT Topology Migration Report

## 1. Versioned migration table

| Legacy representation | Canonical representation | Migration behavior | Semantic equivalence | Checkpoint impact | Result impact | Deprecation status |
|---|---|---|---|---|---|---|
| Decentralized `0/keep` | `KEEP=0` | Exact mapping under `decentralized-binary-v1` | Exact | Binary heads remain index-versioned | Historical IDs retain meaning | Supported compatibility |
| Decentralized `2/line` | `LINE=2` | Exact mapping | Exact persistent-role shape | No tensor change | Historical IDs retain meaning | Supported compatibility |
| Decentralized `1/split` | None | Structured retired result | Not equivalent | Cannot load as COMPACT | Preserved as retired SPLIT | Retired |
| Centralized action `0/keep` | `KEEP=0` | Exact topology mapping under `centralized-actions-v1` | Grid shape equivalent | Legacy action head unchanged | Source commit required | Supported compatibility |
| Centralized action `1/compress` | None | Structured `compress-action` result | Scaled KEEP action, not COMPACT | Must not reinterpret output index | Existing runs remain COMPRESS actions | Legacy action only |
| Centralized action `2/line` | `LINE=2` | Shape mapping; persistent assignment required for new runtime | Slot set equivalent, runtime assignment differs | Legacy model unchanged | Historical centralized sort preserved | Compatibility with caveat |
| Centralized `3/split_hint` | None | Structured retired result | Not equivalent | Three-way heads require legacy vocabulary | SPLIT results remain historical | Retired |
| Centralized `4/recover` | None | Structured `recover-action` result | Lifecycle/scale action, not topology | Must not map to registry output | Historical recovery action preserved | Legacy action only |
| Binary head index `0` | KEEP | `binary-keep-line-head-v1` | Exact | No tensor reshape | None | Supported compatibility |
| Binary head index `1` | LINE | `binary-keep-line-head-v1` | Exact | Distinct from runtime numeric ID 1 | None | Supported compatibility |
| Three-way head indices `0/1/2` | KEEP/LINE/retired SPLIT | `legacy-structural-head-v1` | Third head has no primary mapping | Old checkpoint remains readable only with old vocabulary | No result relabeling | Deprecated vocabulary |
| Alias `grid/nominal` | KEEP | Explicit `legacy-name-aliases-v1` only | Shape alias | None | None | Compatibility alias |
| Alias `two_column/reduced_footprint` | COMPACT | Explicit migration only | Exact new registry geometry | No historical checkpoint assumed | Phase 3+ only | Supported alias |
| Alias `single_file` | LINE | Explicit migration only | Exact | None | None | Compatibility alias |
| WEDGE or unknown numeric | None | Explicit unsupported result | None | Loading fails | No result reinterpretation | Unsupported |

## 2. Checkpoint handling

Inspected historical checkpoints do not contain an explicit topology vocabulary.
Recognized binary methods map to `binary-keep-line-head-v1`; recognized old RVT
three-head methods map to `legacy-structural-head-v1`. Unknown methods without
`topology_vocabulary_version` fail. Tensor output width alone is never used to
infer semantics.

No checkpoint is rewritten, reshaped, or declared compatible with a new COMPACT
head. Phase 3 performs no model reconstruction.

## 3. KEEP/LINE migration classification

- KEEP centering for incomplete rows is **A: representation-only**. It subtracts
  one common translation, leaving pairwise offsets and Metric V3 unchanged.
- LINE persistent-index construction is **A: representation-only** relative to
  the selected decentralized base and exactly preserves its slots/ranks.
- Legacy centralized state-sorted LINE remains a compatibility path and is not
  claimed equivalent as a robot-to-role mapping after robots exchange order.

No category B/C correction and no category D regression was found.

## 4. Legacy implementation isolation

`config.TOPOLOGY_ACTIONS`, centralized environment/controller geometry, ROS 2
formation tables, old script-local dictionaries, and model-head constants remain
for source-commit reproducibility. They are explicitly legacy and are not the
primary registry authority. New topology code must use
`rvt_swarm.topology_registry`.

## 5. Result validity

No historical result, manifest, trace, or checkpoint is modified or invalidated.
Historical outputs remain interpretable under their exact source commit and
legacy vocabulary. They must not be pooled with future publication results after
the final method freeze.

Phase 3 generated no scientific result.
