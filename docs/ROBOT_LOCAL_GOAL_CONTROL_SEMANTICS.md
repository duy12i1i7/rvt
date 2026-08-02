# Robot-Local Goal Control Semantics

The shared Phase 6 mission goal is a static world-frame goal for the topology
origin. Robot i converts it to an own target using only its registry-provided
role offset:

`p_i_target = p_goal_origin + R(psi_mission) r_i^tau`.

The local goal acceleration is a bounded direction/magnitude request:

`u_i_goal = a_max * k_goal * ball_clip((p_i_target - p_i) / spacing, 1)`.

Velocity damping is reported separately as

`u_i_damp = -a_max * k_damp * v_i / v_max`.

No swarm centroid, average position, global progress, front/rear robot, world
corridor inference or current full formation template is used. The mission
direction is a shared immutable command. Translation of all positions and the
goal by the same vector leaves the action unchanged. Rotating own state,
mission direction, goal and local geometry rotates the action consistently.
