# Robot-Local Controller and Safety Stack

Phase 6 uses one shared controller for KEEP, COMPACT and LINE. For observer i
and forced topology tau, only fresh one-hop peers on tau's registry neighbour
slice contribute to formation control.

Let `a_max`, `v_max` and `s` denote immutable maximum acceleration, maximum
speed and nominal formation spacing. The world-frame pairwise residual is

`e_ij = (p_j - p_i) - R(psi) d_ij^tau`.

The controller terms are

`u_form = a_max * k_form * mean(e_ij / s)`,

`p_i_goal = p_goal_origin + R(psi) r_i^tau`,

`u_goal = a_max * k_goal * ball_clip((p_i_goal - p_i) / s, 1)`,

`u_damp = -a_max * k_damp * v_i / v_max`,

and `u_obs`, the documented local obstacle response. The unbounded base action
is their sum. The safety projection computes the nearest feasible own action to
that sum under local half-spaces and the physical acceleration ball. A final
norm clip enforces the physical action bound.

All gains are the previously declared shared `RuntimeConfig.controller` gains.
No topology-specific or team-size-specific gain exists. Missing formation
neighbours contribute no invented residual. A zero-neighbour robot still has
goal, damping, obstacle and safety terms.

The shared static goal is the desired origin of the centered topology, not the
current swarm centroid and not a per-step global progress target. Because every
template is centered for evaluation and pairwise offsets are translation
invariant, role-local targets and the pairwise controller agree without runtime
centroid access.

The stack returns one action for one robot. The centralized test simulator may
call it once per robot and stack the results only after every local evaluation
has completed.
