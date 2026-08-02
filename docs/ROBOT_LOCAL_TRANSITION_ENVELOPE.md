# Robot-Local Transition Envelope

For robot i, the static role displacement is
`Delta_i(a,b) = r_i^b - r_i^a` in the shared mission frame.  The runtime input
contains only i's source and target local topology slices, own pose/velocity,
fresh one-hop peers, local obstacle primitives, and immutable bounds.

The dynamic envelope is a clearance-inflated capsule covering the role-motion
segment reachable before the next mandatory local recertification plus braking.
Its lateral extent also covers the complete role-specific source-to-target
displacement from the registry.  Longitudinal motion is covered inductively by
recertification over the configured lookahead; the protocol does not pretend a
sensor can certify an arbitrarily distant full rollout.

Prediction horizon is derived from control period, bounded message delay, speed,
and maximum acceleration.  Footprint inflation uses robot-obstacle clearance
and transition margin.  Required observation extent is compared directly with
the local sensing range.  The result reports displacement, capsule endpoints,
horizon, required and observed extents, completeness, and an unsupported reason.

Incomplete coverage, stale required peers, nonfinite state, invalid topology
slices, or bounds inconsistent with Phase 6 action semantics produce UNKNOWN.
The API accepts no environment, map, corridor, exit plane, joint state, future
rollout, centroid, or success label.
