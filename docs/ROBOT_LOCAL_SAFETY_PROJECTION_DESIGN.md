# Robot-Local Safety Projection Design

Design frozen before Phase 6 closed-loop evaluation: Option B, an exact
two-dimensional per-robot convex projection. The only decision variable is
robot i's world-frame acceleration `u_i`.

## Objective and physical bound

The projection solves

`minimize ||u_i - u_i_base||^2`

subject to `||u_i|| <= a_max` and locally derived peer/obstacle half-spaces.
All quantities are SI. The solver enumerates the interior candidate, each
half-space boundary, line-circle intersections and pairs of half-space
boundaries. This is deterministic active-set enumeration in two dimensions;
there is no external numerical optimizer and no iteration budget.

## One-step half-spaces

The constraints match the simulator's semi-implicit update. For relative
center vector `x = p_i - p_threat`, outward unit normal `n = x / ||x||`, relative
velocity `v_rel` and control period `dt`, requiring projected one-step clearance
`d_safe` gives

`n^T u_i >= (d_safe - ||x|| - n^T v_rel dt) / dt^2 + a_threat`.

For a peer, `a_threat = a_max` is the declared worst-case peer acceleration
toward robot i. For an obstacle, `a_threat = 0` because locally observed
obstacle velocity is already included and no obstacle acceleration is assumed.

Peer clearance is `2 robot_radius + inter_robot_safety_margin`. Obstacle
clearance follows the local obstacle-response contract. A stale peer's
clearance is inflated by `v_max * message_age`; obstacle uncertainty adds
`v_max * age + (1-confidence) * robot_radius`. These assumptions are
conservative local bounds, not predictions of another action.

Only threats within the corresponding local communication/sensing range are
eligible. A half-space that the bounded proposed action already satisfies is
retained for validation but does not cause an intervention.

## Ordering, feasibility and failure

All constraints are canonicalized by threat kind and local source key before
solving, so input ordering cannot change the result. The disk and half-spaces
are solved jointly, not sequentially.

If the intersection is empty, the output is an explicit
`infeasible_conservative_fallback`: maximum bounded acceleration along the
weighted sum of outward normals, with the most urgent normal used when the sum
cancels. This fallback is finite, bounded, logged and cannot return the unsafe
unprojected action silently. It does not claim to satisfy an impossible set.

Malformed or nonfinite local inputs fail closed with a zero bounded action and
an explicit invalid/failure diagnostic. Solver failure and infeasibility are
separate statuses.

## Limitations

The half-spaces enforce a one-step local geometric condition under bounded peer
acceleration and the executed dynamics. They do not optimize another robot's
action, coordinate constraints across robots or prove recursive/global
feasibility. Consequently this component is called a robot-local safety
projection, not a whole-swarm CBF-QP guarantee.
