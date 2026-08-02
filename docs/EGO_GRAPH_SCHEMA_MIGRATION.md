# Ego Graph Schema Migration

## Version policy

The authoritative future schema is `rvt-ego-graph/v2`. Its normalization and
serialization versions are independently recorded as
`rvt-ego-normalization/v1` and `rvt-ego-graph-serialization/v1`.

A canonical record includes:

- graph, normalization, serialization, and topology-registry versions;
- SHA-256 of the ordered feature registry;
- SHA-256 of the immutable runtime configuration;
- units for each feature block;
- observer, lifecycle, timestamp, committed, candidate, and root metadata;
- node/edge tensors and all validity masks;
- content SHA-256.

Objects are closed schemas. Unknown or missing fields, invalid shapes, unknown
versions, a mismatched runtime configuration, changed units, non-canonical
records, and content tampering are rejected.

## Supported operation

V2 to V2 round-trip is deterministic. Canonical peer and obstacle ordering is
for serialization and regression identity; it does not grant semantic meaning
to a raw input index. Deserialization reconstructs typed tensors and reruns all
graph invariants before accepting the record.

## Explicitly unsupported reinterpretation

The following tensor schemas cannot be shape-cast to V2:

| Source | Widths | Reason conversion is unsafe |
|---|---:|---|
| historical whole-swarm graph | 68/11 | global semantics, absolute/joint features, no local root boundary |
| decentralized ego graph V1 | 28/9 | no version/config hash, no masks, no COMPACT, different units and feature order |

`migrate_legacy_ego_graph_schema` therefore rejects these schemas. A valid V2
migration must rebuild the graph from the original `RobotView`, the exact
immutable runtime configuration, and the observer's exact local topology
slice. If any of those sources is unavailable, migration is not scientifically
valid.

Historical checkpoint readers remain attached to their original schemas. V2
does not claim checkpoint compatibility and Phase 4 does not train or alter a
model.
