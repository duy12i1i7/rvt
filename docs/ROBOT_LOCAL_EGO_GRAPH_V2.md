# Robot-Local Ego Graph V2

## Status and authority

`rvt-ego-graph/v2` is the authoritative graph schema for future deployable
inference. Phase 4 defines the representation only. The active Phase 1
selector remains on ego-graph V1 until Phase 5 reconstructs and validates its
model heads.

Implementation: `rvt_swarm.decentralized.ego_graph_v2`.

The builder accepts exactly one `RobotView`, one immutable `RuntimeConfig`, one
robot-local topology slice, one candidate topology ID, and one local
observation step. There is no argument for joint state, a complete graph, a
complete topology template, a map, a label, or an outcome.

## Node classes and ordering

One graph contains:

1. exactly one SELF node at index 0;
2. zero or more fresh physical PEER nodes, canonically ordered by robot ID;
3. zero or more LOCAL OBSTACLE nodes, canonically ordered by local geometry.

An unobserved entity is omitted. It is never represented as a zero-valued real
node. Single graphs therefore have all-true node and edge validity masks.
Per-feature masks distinguish applicable, measured, and missing blocks.

Node tensor width is 35, in this fixed block order:

| Columns | Feature block |
|---|---|
| 0:3 | node kind one-hot |
| 3:5 | mission-frame relative position / nominal spacing |
| 5:7 | mission-frame relative velocity / maximum speed |
| 7:8 | class-specific distance / communication or sensing range |
| 8:10 | bearing `(cos, sin)` |
| 10:13 | committed topology one-hot |
| 13:16 | candidate topology one-hot |
| 16:18 | candidate role offset / nominal spacing |
| 18:20 | own candidate role displacement / nominal spacing |
| 20:21 | own transition magnitude / nominal spacing |
| 21:22 | local transition observation extent / sensing range |
| 22:24 | goal vector / nominal spacing |
| 24:25 | goal distance / nominal spacing |
| 25:27 | own velocity / maximum speed |
| 27:28 | local progress / nominal spacing |
| 28:29 | local decision age / configured reference |
| 29:30 | peer message age / stale limit |
| 30:31 | peer candidate-role-known flag |
| 31:32 | peer committed-topology conflict flag |
| 32:33 | obstacle radius / sensing range |
| 33:34 | obstacle confidence |
| 34:35 | obstacle age / control period |

The code-level feature registry and its SHA-256 digest are authoritative. The
human-readable classification is in `RVT_EGO_GRAPH_FEATURE_REGISTRY.md`.

## Edge semantics

Every admitted peer or obstacle has two root-incident directed edges. There
are no peer-to-peer edges.

| Type | Direction | Meaning |
|---|---|---|
| 0 | SELF to PEER | current one-hop communication observation |
| 1 | PEER to SELF | reverse message-passing direction |
| 2 | SELF to OBSTACLE | current local sensing relation |
| 3 | OBSTACLE to SELF | reverse message-passing direction |

Edge tensor width is 19: edge type one-hot `0:4`, relative position `4:6`,
relative velocity `6:8`, normalized distance `8:9`, bearing `9:11`, nominal
formation relation `11:12`, desired pairwise offset `12:14`, local formation
residual `14:16`, and candidate topology one-hot `16:19`.

Desired pairwise geometry is valid only when the currently observed peer is a
nominal neighbour in the observer's local candidate slice. No edge asserts a
communication relation between two peers.

## Freshness and message classes

A physical peer node requires a valid `NeighbourRecord`, non-self nonnegative
sender ID, valid link, primary committed topology, nonnegative age no greater
than the configured stale bound, finite relative position, and current range
within `R_comm`.

Exact duplicates collapse. The freshest record wins over older records. Two
different records from the same sender with the same freshest age are
conservatively omitted. Missing peer velocity produces zeros with the velocity
feature mask false. Lost and stale peers are omitted immediately.

Physical peer state messages differ from protocol messages:

- Physical peer state messages may create one-hop physical nodes.
- Protocol event tokens may propagate event identity but do not create a
  physical node for a multi-hop origin.
- Consensus scalar messages update a local protocol scalar but do not carry a
  remote robot state or ego graph.

## Topology conditioning

Static mission setup may read the full Phase 3 registry. It reduces that data
to `RobotLocalTopologyMetadata` for one observer. Runtime graph construction
receives only the observer's KEEP, COMPACT, and LINE role offsets plus desired
pairwise offsets for that observer's nominal neighbours.

The graph exposes candidate ID, own candidate offset and displacement, local
transition extent, and pairwise candidate geometry only for currently observed
peers. It exposes no complete template, global width or length, all-role offset
table, or global candidate feasibility value.

## Batching and consumer contract

`batch_robot_local_ego_graphs` builds a canonical disjoint union with no fixed
maximum N, peer count, or obstacle count. `graph_index`, `edge_graph_index`, and
`root_index` preserve graph boundaries and self identity. Candidate topology
and observer IDs remain explicit. No edge may cross a graph boundary.

Future robot-level outputs must be read from each graph's root representation.
Message passing and pooling over that robot's own locally observable nodes are
local operations. Aggregation across ego graphs or over the complete swarm is
prohibited in deployable inference.

## Versioning and compatibility

Normalization version is `rvt-ego-normalization/v1`; serialization version is
`rvt-ego-graph-serialization/v1`. Records include the feature-schema hash,
topology-registry version, runtime-configuration hash, masks, and units.

V1 and the legacy global 68x11 schema are not shape-cast into V2. Migration
requires rebuilding from the original `RobotView`, immutable configuration,
and robot-local topology slice. Historical paths remain explicit compatibility
paths and cannot be imported by the strict decentralized namespace.
