# Decentralized Configuration Contract (Task G1)

`rvt_swarm/decentralized/parameters.py`. Four strictly separated classes; every
deployable decision threshold must come from one of them.

## A — PlatformParams (physical, measured not chosen)

| field | units | source | runtime | valid range |
|---|---|---|---|---|
| `robot_radius` | m | `EnvConfig.robot_radius` | yes | > 0 |
| `collision_clearance_obstacle` | m | `EnvConfig.min_ro_distance` | yes | > `robot_radius` |
| `collision_clearance_robot` | m | `EnvConfig.min_rr_distance` | yes | > 2·`robot_radius` |
| `max_speed`, `max_accel` | m/s, m/s² | `EnvConfig` | yes | > 0 |
| `obstacle_sensor_range` | m | `EnvConfig.lidar_range` | yes | > 0 |
| `communication_range` | m | protocol assumption | yes | > 0 |
| `control_period`, `communication_period` | s | `EnvConfig.dt` | yes | > 0 |

Robot–obstacle clearance is measured to the obstacle **centre**, matching
`environment.py:566`.

## B — MissionParams (what the mission demands, SI)

| field | units | value | note |
|---|---|---|---|
| `nominal_spacing` | m | 0.9 | formation lattice pitch |
| `formation_tolerance` | m | 0.55 | **FROZEN** ε_form |
| `recovery_dwell_seconds` | s | 3.0 | **FROZEN** — derives L_recover = 20 |
| `safety_margin` | m | 0.0 | added to every clearance requirement |

## C — ProtocolParams (assumptions required for correctness)

| field | units | value | violating it breaks |
|---|---|---|---|
| `max_team_size` | — | 6 | the diameter bound below |
| `max_component_diameter` | hops | `None` → `N_max − 1` | trigger/confirm coverage |
| `max_message_age_seconds` | s | 0.45 | staleness rejection |
| `evidence_persistence_seconds` | s | 0.45 | noise immunity |
| `event_collection_seconds` | s | 0.0 | — arming and propagation share a step |
| `commitment_seconds` | s | 1.5 | oscillation bound |
| `rearm_inactive_seconds` | s | 3.75 | same-event re-arming |
| `connectivity_assumption` | text | per-component | swarm-wide agreement claims |

## D — Derived (never independently configurable)

```
recovery_dwell_steps        = ceil(3.0  / T_ctrl) = 20
evidence_persistence_steps  = ceil(0.45 / T_ctrl) = 3
commitment_steps            = ceil(1.5  / T_ctrl) = 10
max_message_age_steps       = ceil(0.45 / T_ctrl) = 3
rearm_inactive_steps        = ceil(3.75 / T_ctrl) = 25
D_max                       = max_component_diameter or (max_team_size − 1) = 5
k_trigger = k_confirm       = D_max = 5
forward_sector_half_width_i = |lat(r_i^KEEP) − lat(r_i^LINE)| + clearance + margin
lookahead_distance          = min(R_obs, v²/2a + v·T_protocol + margin)
```

Every derived value reproduces its previously frozen counterpart at
`T_ctrl = 0.15 s`, except `k_trigger`/`k_confirm`, which the audit showed were
unsound at 4.
