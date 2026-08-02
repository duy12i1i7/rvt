# COMPACT Topology Design

## 1. Design constraints

COMPACT is a new structural topology, not an alias for legacy COMPRESS. It must
use the frozen `FormationConfig.nominal_spacing_meters`, preserve the declared
robot clearance, reduce lateral width relative to KEEP, and remain less
longitudinally elongated than LINE. Selection is based only on geometry and
compatibility with the existing pairwise controller. No closed-loop or learned
model result is used.

Template coordinates use `+x` along the shared mission direction and `+y`
lateral to it. All candidate templates are centered before use.

## 2. Candidate A: two-column rectangular lattice

Construction:

```text
columns = 2
row, column = divmod(role_ordinal, 2)
x = row * nominal_spacing
y = (0.5 - column) * nominal_spacing
center all offsets
```

| Property | Result |
|---|---|
| Lateral width | `d` for every `N >= 2`; strictly below KEEP for the Phase 3 matrix |
| Longitudinal length | `(ceil(N/2)-1)d`; approximately half the LINE length |
| Minimum clearance | `d`, including incomplete final rows |
| Nominal graph | Rectangular ladder: row and column adjacency |
| Degree | Maximum 3, independent of N |
| KEEP transition | Reorients the square-like KEEP block into a narrower two-column block |
| LINE transition | Collapses one lateral column while stretching row spacing into one file |
| Controller compatibility | Exact existing pairwise-offset interface; all graph edges have length `d` |
| Sensor requirement | Maximum lateral role displacement plus existing clearance terms |
| Likely use | Moderately constrained regions that do not require single file |
| Limitation | Length grows linearly at roughly `N/2`; forced-topology closed-loop qualification is deferred |

The construction is deterministic and uses no map width, corridor coordinates,
robot state ordering, or model output.

## 3. Candidate B: staggered triangular strip

Construction considered:

```text
x_i = (i-(N-1)/2) * d/2
y_i = alternating +/- sqrt(3)*d/4
```

Consecutive roles are one nominal spacing apart and form a zig-zag strip.

| Property | Result |
|---|---|
| Lateral width | `sqrt(3)d/2`, narrower than KEEP |
| Longitudinal length | `(N-1)d/2`, approximately half the LINE length |
| Minimum clearance | `d` only if second-neighbour geometry is included at `d`; otherwise denser variants fall below the controller's active clearance range |
| Nominal graph | Triangular strip, normally degree up to 4 |
| Degree | Bounded by 4 |
| KEEP transition | Moderate lateral and longitudinal displacement |
| LINE transition | Small for the N=5 endpoint roles under the frozen role-aware tube metric |
| Controller compatibility | Geometrically plausible, but more graph edges and diagonal tracking than the existing grid controller has qualified |
| Sensor requirement | Similar lateral envelope to Candidate A |
| Likely use | Smooth single-file entry and staggered packing |
| Limitation | At N=5 its role-aware separation from LINE is too close to, or inside, the frozen `2*epsilon_form` tube threshold depending on dense-strip spacing |

A denser staggered strip could increase distinction from LINE, but then same-lane
roles approach below nominal spacing and activate the existing avoidance kernel
at the desired set point. That would require controller redesign or tuning,
which Phase 3 forbids.

## 4. Selection

**Candidate A, the two-column rectangular lattice, is selected.**

Reasons:

1. it is a genuine topology distinct from KEEP and LINE;
2. every nominal nearest-neighbour edge remains exactly one configured spacing;
3. its graph is a sparse bounded-degree ladder already expressible by the
   verified pairwise controller;
4. it is mechanically distinguishable under the frozen Metric V3 tolerance for
   every required `N`;
5. it avoids introducing a new packing ratio, controller gain, or tuned scale.

The intended semantics are:

- **KEEP:** nominal square-like mission grid;
- **COMPACT:** reduced-width two-column mission-aligned block;
- **LINE:** maximally narrow single file along the mission direction.

COMPACT controller status in Phase 3 is
`mechanically-compatible; pending forced-topology qualification in Phase 6`.
This document makes no closed-loop success claim.
