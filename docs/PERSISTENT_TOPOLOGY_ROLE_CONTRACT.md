# Persistent Topology Role Contract

## 1. Identity model

Robot identity and topology geometry are separate.

At static mission setup, `generate_persistent_roles` canonicalizes unique robot
keys, sorts the keys deterministically, and assigns contiguous role IDs:

```text
role-0000, role-0001, ..., role-(N-1)
```

Integer robot keys are encoded as fixed-width nonnegative values; string keys
carry an explicit string prefix. Input array order therefore cannot change the
robot-to-role mapping. Duplicate, negative, empty, boolean, or unknown keys are
rejected.

Role IDs indicate no leader, root, coordinator, or priority. The ordinal is a
canonical geometry slot, not runtime authority.

## 2. Topology mapping

Each primary topology maps the same persistent role to one offset:

```text
r_i^tau = role_offset(tau, role_id_i, N, FormationConfig)
```

Switching topology changes `r_i^tau`; it does not change `role_id_i`. Every
template has exactly one offset per role and all three templates have identical
role-ID tuples.

For the compatibility `RoleAssignment` adapter:

- `keep`, `compact`, and `line` are registry-generated tables;
- `from_index(N,d)` maps robot integer identity directly to persistent ordinal;
- the historical mission-setup LINE rank remains a static boundary adapter for
  spawn-compatible ranking and is never called by a control step.

There is no runtime role election, reassignment, bidding, or team-membership
change in Phase 3.

## 3. Serialization

Persistent role JSON uses `rvt-persistent-roles/v1` and stores, for each role:

```text
role_id | canonical robot_key | ordinal
```

Loading is strict: unknown/missing fields, duplicate IDs/keys, noncontiguous
ordinals, or a schema mismatch fail explicitly. The reloaded role set is frozen.

If a legacy role ID is absent from the provisioned set, lookup raises
`TopologyRegistryError`; no nearest slot or replacement role is selected.

## 4. Robot-local information

At deployable runtime robot `i` needs only:

- its persistent role ID;
- committed canonical topology ID;
- its topology-specific own offset;
- neighbour role IDs provisioned for the nominal formation graph;
- locally required desired pairwise offsets;
- the shared mission direction.

`RuntimeTopologyRoleView` contains exactly these static geometry values. It has
no full role table, joint position array, swarm centroid, global graph, map, or
topology decision.

The existing KEEP/LINE beacons still carry two compatibility role coordinates.
No wire extension or new communication phase is introduced in Phase 3.

## 5. Out-of-scope membership behavior

A failed robot leaves its slot unfilled. Surviving robots retain their role IDs.
Dynamic membership, role repair, and attrition-aware reassignment remain outside
the declared method.
