# Local Obstacle Graph Representation

## Chosen representation

V2 uses one node per locally visible obstacle primitive. This matches the
current local sensor interface, supports variable obstacle count without a
fixed angular grid, and does not need simulator polygon vertices or global map
identity. The choice was made from observability and scaling constraints, not
from learned success.

Accepted inputs are `LocalObstacleObservation` records or historical local
tuples `(dx, dy, radius)` and `(dx, dy, radius, dvx, dvy)`. Tuple compatibility
does not grant access to any map-level data.

## Admission

An obstacle node is admitted only when:

- its record is structurally supported and marked valid;
- center, radius, confidence, and age are finite;
- radius is nonnegative and confidence lies in `[0, 1]`;
- age is nonnegative and no greater than one control period;
- its locally observed center lies within `R_obs`.

Invalid, stale, or out-of-range records are omitted. Exact duplicate local
records collapse. Missing or invalid obstacle velocity is represented by zero
values with a false velocity mask.

## Geometry

The raw center vector is transformed into the shared mission-aligned frame.
For center vector `c` and radius `r`, the represented point is the closest point
on the primitive to the robot:

```text
d_center = ||c||
d_clear = max(d_center - r, 0)
p_close = 0                         if d_center = 0
p_close = c * d_clear / d_center    otherwise
```

The node stores `p_close / nominal_spacing`, `d_clear / R_obs`, center bearing
as `(cos, sin)`, `r / R_obs`, confidence, age/control-period, and measurable
relative velocity / maximum speed. The range gate uses the observed center,
not unseen polygon extent.

Every obstacle has SELF-to-OBSTACLE and OBSTACLE-to-SELF edges. The edge
geometry is root-relative and no obstacle-obstacle relation is inferred.

## Identity boundary

`obstacle-local:NNNN` is a canonical record-local serialization key. It is not
a simulator obstacle ID and has no semantic persistence across observations.
V2 does not use global obstacle IDs, polygon ordering, corridor labels,
passage families, map boundaries, or obstacle data outside `R_obs`.
