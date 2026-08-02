# Local Versus Global Graph Aggregation

## Allowed local aggregation

One `RobotLocalEgoGraph` is robot i's local observation set: self, fresh
one-hop physical peers, and locally sensed obstacles. Message passing from
those nodes into the SELF root and pooling over only those nodes are local
operations. They do not imply that robot i knows the complete swarm.

Future robot-level model outputs must be read from the SELF/root embedding.
Peer and obstacle aggregation must respect per-feature masks and the root of
the same graph.

## Prohibited global aggregation

Deployable inference may not:

- pool nodes from different robots' ego graphs;
- pool a complete whole-swarm graph;
- mix graphs through batch statistics;
- reconstruct unseen robots through a graph-level token;
- run complete-swarm attention or all-reduce;
- normalize with joint-state or dataset-final statistics.

Central batching is permitted for offline training only when it is a disjoint
union of independently valid local samples. `graph_index`,
`edge_graph_index`, and `root_index` preserve these boundaries; construction
asserts that no edge crosses them.

## Static enforcement

`rvt_swarm.decentralized.guards` rejects known global pooling calls and imports
of `dataset` or `legacy_global_graph` inside the strict deployable namespace.
The V2 graph itself contains only root-incident edges and no peer-to-peer edge.

Historical global pooling remains in `rvt_swarm.models` for historical
checkpoint interpretation. The historical global builder is isolated under
`rvt_swarm.legacy_global_graph`; neither module is part of the strict V2 path.
