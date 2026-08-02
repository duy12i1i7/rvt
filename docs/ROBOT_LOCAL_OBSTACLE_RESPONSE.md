# Robot-Local Obstacle Response

The Phase 6 base controller consumes only locally observed circle primitives.
An observation is eligible only when valid, finite and within `R_obs`.
Ordering and any map-level identity are irrelevant.

For obstacle k, let n point from its center toward robot i. The required center
clearance is

`d_safe = robot_radius + max(observed_radius, obstacle_clearance_margin)`.

The declared margin already contains the nominal obstacle radius and physical
surface margin. The `max` preserves at least physical clearance for a larger
observed primitive without introducing a scenario-specific radius.

The response distance is derived from physical braking:

`d_response = min(R_obs, d_safe + v_max^2 / (2 a_max))`.

Proximity severity grows linearly from zero at `d_response` to one at
`d_safe`. Closing-speed severity uses the same stopping-distance equation with
the observed relative closing speed. The larger severity multiplies
`a_max * obstacle_clearance_gain * n`; valid obstacle vectors are averaged.

Parameter classification:

| Quantity | Classification |
|---|---|
| robot radius, obstacle radius | physical geometry / local observation |
| obstacle clearance margin | declared safety margin |
| maximum speed and acceleration | physical platform limits |
| braking distance | derived lookahead quantity |
| `R_obs` | sensor limitation |
| obstacle clearance gain | frozen controller design parameter |

No obstacle gives exactly zero response. An out-of-range, invalid or
unobserved primitive has no effect. Age and confidence never provide evidence
that space is safer; uncertainty can only inflate the safety projection's
clearance. The response is local collision mitigation, not a global map-based
planner.
