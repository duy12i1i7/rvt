# Phase 8E F9 Dynamic Obstacle Execution Contract

## Authoritative choice

F9 stores both `obstacle_speed_mps` and timestamped waypoints. They are
inconsistent in every nonfinal layout:

| Layout | Declared speed (m/s) | Waypoint-implied speed (m/s) |
|---|---:|---:|
| train-f9-00 | 0.150000 | 0.416667 |
| train-f9-01 | 0.163200 | 0.388199 |
| validation-f9-00 | 0.201600 | 0.323834 |

Timestamped waypoints are authoritative because each is a complete
position-time constraint and supports deterministic interpolation and snapshot
replay. The speed parameter remains an audit-only family-range descriptor. A
constant-declared-speed alternative was rejected because it cannot reach the
frozen endpoint at the frozen time. No label, candidate result or final-test
record informed this choice.

## Motion

Each obstacle is a closed circle with stored radius. For adjacent waypoints
`(q_k,t_k)` and `(q_{k+1},t_{k+1})`, at absolute episode time `t`:

`q(t)=q_k + ((t-t_k)/(t_{k+1}-t_k))*(q_{k+1}-q_k)`.

Velocity is constant segment displacement divided by duration. Acceleration is
zero inside a segment and velocity changes atomically at waypoint time. Before
the first waypoint, hold its pose with zero velocity. After the final waypoint,
hold the final pose with zero velocity. There is no loop, reflection, phase
randomization or trajectory resampling. Absolute phase is zero.

Robot-dynamic collision is checked continuously between control boundaries using
linearly interpolated robot and obstacle centers and the frozen circle-clearance
threshold. Boundary contact is collision.

## Observation, snapshot and matching

A robot receives only current ego-relative center, current relative velocity and
radius when center distance is at most `R_obs`. Latency and position/velocity
noise are explicitly disabled. Waypoints, future velocity changes and terminal
pose are never robot-visible.

Snapshot state is segment index, episode time, position and velocity. Restoring
the snapshot reproduces the same trajectory exactly. Both candidate clones start
with identical dynamic snapshot and dynamic-obstacle seed identity. The current
v1 path consumes no random dynamic draw, which is explicit rather than an
implicit zero-noise default.

Nonpositive radius, nonfinite waypoint, fewer than two waypoints, nonincreasing
time or state inconsistent with the interpolation formula is
`GEOMETRY_INVALID` or `SCHEDULE_INVALID`, never an ordinary negative label.
