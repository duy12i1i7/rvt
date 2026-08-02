# Ego Graph Coordinate and Normalization Contract

## Mission-aligned frame

The graph origin is robot i's current position. The longitudinal unit axis is
the normalized shared static mission direction `e_x`; the lateral unit axis is
`e_y = (-e_x.y, e_x.x)`. A world-frame local vector `v` becomes:

```text
v_mission = (dot(v, e_x), dot(v, e_y))
```

Own world position never enters a geometric feature directly. Peer positions
arrive as relative one-hop measurements. Obstacle centers arrive as relative
local sensor measurements. The goal vector is `goal - own_position`. Role
offsets and desired offsets are already expressed in the mission-aligned
template frame by the authoritative topology registry.

Velocity vectors use the same rotation. Bearings are represented as unit
`(cos, sin)` vectors, avoiding angular discontinuity. A zero-length vector gets
zero bearing with its bearing mask false.

This contract is translation invariant. If the physical scene and mission
heading are jointly rotated, mission-frame features remain consistent. No
world-map coordinate, dataset centroid, or dataset-wide statistic is needed.

## Declared normalization

| Quantity | Normalization source |
|---|---|
| peer/obstacle/goal/role position | nominal formation spacing |
| own, peer, obstacle velocity | physical maximum speed |
| peer distance | communication range `R_comm` |
| obstacle clearance and radius | obstacle sensing range `R_obs` |
| message age | configured maximum message-age rounds |
| obstacle age | physical control period |
| decision age | configured decision-reference steps, clamped to `[0,1]` |
| confidence and flags | already dimensionless |

The local transition observation extent is derived from own candidate lateral
displacement, robot radius, obstacle clearance, controller response bound,
protocol drift bound, and transition observation margin, then divided by
`R_obs`. No measured distribution or final-test statistic selects a constant.

The runtime configuration is immutable and hashed into every serialized graph.
Changing a physical normalization source requires a different configuration
hash; loading a graph under a mismatched configuration is rejected.

## Numerical and missing-value policy

All tensors are finite `float32`; indices and classes are `int64`; validity
masks are Boolean. Missing measurable velocity uses zero only together with a
false feature mask. Stale or invalid entities are omitted. Applicability masks
distinguish legitimate zero from unavailable data.

Mechanical tests cover translated scenes, 90-degree rotation, different
mission headings, and normalization from the declared configuration.
