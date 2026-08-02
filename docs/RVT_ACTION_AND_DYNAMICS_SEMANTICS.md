# RVT Action and Dynamics Semantics

## Confirmed action meaning

The current simulator's two-dimensional action is world-frame planar
acceleration in m/s^2. This is established by the executed integration in
`SwarmFormationEnv.step`, not by variable naming:

1. each action vector is norm-clipped to `maximum_acceleration = 0.6 m/s^2`;
2. velocity is updated as `v[k+1] = v[k] + u[k] * dt`;
3. velocity is norm-clipped to `maximum_speed = 0.9 m/s`;
4. position is updated as `p[k+1] = p[k] + v[k+1] * dt`;
5. obstacle positions are advanced;
6. centralized simulator collision resolution runs after the position update.

The control period is `dt = 0.15 s`. This is semi-implicit Euler because the
new velocity is used for the position update. The simulator applies no action
delay. The current command affects velocity and position in the same step.

## Saturation and collision ordering

Action saturation is radial norm clipping, not component-wise clipping.
Velocity saturation is also radial. Historical controllers may clip before
calling the environment, but the environment clips again and is the final
physical bound. Collision resolution changes joint positions and velocities
only after action integration. It is simulator infrastructure and cannot be
claimed as preventive controller safety.

The Phase 6 mechanical integrator uses the same action-clip, velocity-update,
speed-clip and position-update order. A deterministic equivalence test compares
it with `SwarmFormationEnv.step` in a collision-free fixture.

## Phase 5 consistency

The Phase 5 residual action is recorded in m/s^2 and is bounded as a correction
to a future base acceleration. That contract is consistent with the confirmed
simulator action semantics. Phase 6 does not activate or modify the residual.

The ROS differential-drive bridge separately integrates planar acceleration to
a desired velocity before producing Twist commands. It is a platform adapter,
not the authoritative simulator dynamics, and is outside Phase 6 qualification.
