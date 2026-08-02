# Topology Registry Specification

## 1. Authority and versions

`rvt_swarm/topology_registry.py` is the authoritative topology module.

| Contract | Version |
|---|---|
| Registry | `rvt-topology-registry/v1` |
| Definition | `rvt-topology-definition/v1` |
| Persistent roles | `rvt-persistent-roles/v1` |
| Template serialization | `rvt-topology-template/v1` |
| Legacy migration | `rvt-topology-migration/v1` |

The primary scientific order is explicit and fixed:

```text
KEEP(0), COMPACT(5), LINE(2)
```

KEEP and LINE preserve selected-runtime IDs. COMPACT uses ID 5 because legacy
value 1 has conflicting SPLIT/COMPRESS meanings, value 3 means SPLIT_HINT, and
value 4 means the RECOVER action. Registry iteration never derives scientific
order from dictionary ordering.

## 2. Immutable interface

`TopologyDefinition` is frozen and provides:

- stable numeric ID, canonical name, aliases, and semantic description;
- deterministic persistent-role geometry generator;
- topology-specific sparse nominal graph generator;
- local pairwise offset function;
- structured physical-validity checker;
- static transition-geometry provider;
- controller compatibility metadata;
- offline Metric V3 template provider;
- serialization version.

Aliases are metadata, not alternate active names. `get_topology_definition`
accepts only a canonical ID or canonical name. An alias is accepted only by
`migrate_legacy_topology` with an explicit source vocabulary.

`TopologyTemplate`, `PersistentRoleSet`, graph statistics, local views,
transition records, validity records, and migration records are frozen tuples
and dataclasses. Construction inputs are source configuration plus stable robot
identity; no scenario or learned output participates.

## 3. Geometry construction

All offsets are defined in the topology-template frame:

- origin: numerical centroid of role offsets;
- `+x`: shared longitudinal mission direction;
- `+y`: template lateral direction;
- world translation: static mission origin;
- world rotation: proper rotation aligning `+x` with mission direction.

Templates satisfy `sum_i r_i = 0` to numerical tolerance. Translation changes
only the world origin. Rotation preserves distances and rotates every pairwise
offset equivariantly. No map coordinate or corridor orientation appears in any
role generator.

KEEP is the preserved square-like row-major grid with
`ceil(sqrt(N))` columns. Incomplete final rows are deterministically filled by
role ordinal and then centered. Centering is a representation-only translation:
all pairwise offsets and Metric V3 values remain unchanged.

COMPACT is a centered two-column rectangular lattice. It has width `d`, length
`(ceil(N/2)-1)d`, and nearest-role clearance `d`.

LINE is a centered single file along `+x`, with rank spacing `d`, zero lateral
width, and length `(N-1)d`.

Here `d = FormationConfig.nominal_spacing_meters`.

## 4. Graph and local offset contract

The nominal graph is a formation-control graph, not the dynamic communication
graph:

- KEEP: horizontal/vertical adjacency in the square-like grid;
- COMPACT: horizontal/vertical adjacency in the two-column ladder;
- LINE: adjacent-rank chain.

Every edge `(i,j)` exposes:

```text
d_ij^tau = R(mission_direction) (r_j^tau - r_i^tau)
d_ji^tau = -d_ij^tau
```

The graphs are deterministic, connected, sparse, and bounded degree: 4 for
KEEP, 3 for COMPACT, and 2 for LINE. Cycle consistency follows because every
edge offset is a difference of one shared immutable template.

At runtime a robot receives a `RuntimeTopologyRoleView` containing only its role
ID, committed topology ID, own template offset, and desired offsets to nominal
formation neighbours. It contains no full template, joint state, global graph,
centroid, or topology selector.

## 5. Full-template boundary

Full templates are allowed for:

- deterministic initialization and static mission setup;
- persistent role provisioning;
- offline diagnostics and mechanical validity;
- Metric V3/evaluation;
- serialization/provenance.

Robot-local control does not reconstruct or inspect a full template. Phase 3
does not change the existing KEEP/LINE beacon or consensus wire protocol and
does not make COMPACT a runtime-selectable mode.

## 6. Validity and distinction

`TopologyValidityResult` reports support, structured errors/warnings, minimum
clearance, width/length, graph statistics, topology separations, required local
sensor extent, and controller compatibility.

Validation rejects without clamping or substitution:

- role/team count mismatch or duplicate role IDs;
- nonfinite or non-centered offsets;
- clearance below configured requirement;
- disconnected or inconsistent graph geometry;
- overlapping primary Metric V3 tubes when scientific comparison is requested;
- lateral transition observation extent above `R_obs`;
- oversized or invalid team configurations.

Construction support, metric distinction, and experimental eligibility are
separate. The required N matrix passes mechanically, but this phase makes no
closed-loop or learned-model claim.

## 7. Serialization and provenance

Template JSON stores version identifiers, explicit meter units, configurable
source values, derived offsets/edges, persistent roles, and a source SHA-256.
Loading rejects unknown/missing fields and version/unit mismatches, reconstructs
the template from source values, and compares canonical derived JSON. Serialized
derived geometry cannot override the registry.

Historical values require a versioned migration vocabulary. Tensor output width
alone is not accepted as checkpoint topology provenance.

## 8. Scope exclusions

The registry contains no learned selector, ego-graph redesign, residual action,
readiness certificate/consensus, transition state machine, safety projection,
scenario construction, controller tuning, or scientific experiment.
