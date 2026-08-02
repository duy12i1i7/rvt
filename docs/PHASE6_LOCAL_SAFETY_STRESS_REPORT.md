# Phase 6 Local Safety Stress Report

Seven declared one-step local fixtures were evaluated with the base action
alone as a diagnostic and with the authoritative robot-local projection. The
projection receives only the observer state, local peer messages and locally
sensed obstacle primitives. It never invokes the environment collision repair.

The safe-open action was unchanged exactly and produced no false intervention.
Every declared hazard activated either a feasible local projection or the
explicit conservative fallback. The feasible two-sided and moving-obstacle
fixtures collided under the base diagnostic and reached the required 0.55 m
clearance with projection. The fresh-peer projection increased its next-step
distance from 0.4010 m to 0.4135 m. Stale and uncertain observations triggered
the declared uncertainty inflation and conservative fallback.

The intentionally infeasible two-sided fixture remained in collision after the
fallback. This is the expected mechanical limitation of an already empty
one-step feasible set, not solver failure and not evidence of safety. No solver
failure, deadlock or nonfinite action occurred.

| Case | Mode | Collision | dmin (m) | abs(delta u) | Step/duration | Status | Fallback | Progress (m) | False intervention |
|---|---|---:|---:|---:|---|---|---:|---:|---:|
| safe_open | base diagnostic | no | n/a | 0.0000 | - | disabled_diagnostic | no | 0.0135 | no |
| safe_open | projection | no | n/a | 0.0000 | - | unchanged | no | 0.0135 | no |
| static_obstacle_uncertain | base diagnostic | no | 0.5990 | 0.0000 | - | disabled_diagnostic | no | 0.0010 | no |
| static_obstacle_uncertain | projection | no | 0.6135 | 0.6444 | 0/1 | infeasible_conservative_fallback | yes | -0.0135 | no |
| two_sided_restriction | base diagnostic | yes | 0.5435 | 0.0000 | - | disabled_diagnostic | no | 0.0133 | no |
| two_sided_restriction | projection | no | 0.5500 | 0.2910 | 0/1 | local_constraint_projection | no | 0.0068 | no |
| fresh_peer_approach | base diagnostic | no | 0.4010 | 0.0000 | - | disabled_diagnostic | no | 0.0540 | no |
| fresh_peer_approach | projection | no | 0.4135 | 0.5556 | 0/1 | local_constraint_projection | no | 0.0415 | no |
| stale_peer | base diagnostic | no | 0.4365 | 0.0000 | - | disabled_diagnostic | no | 0.0135 | no |
| stale_peer | projection | no | 0.4635 | 1.2000 | 0/1 | infeasible_conservative_fallback | yes | -0.0135 | no |
| moving_obstacle | base diagnostic | yes | 0.5407 | 0.0000 | - | disabled_diagnostic | no | 0.0026 | no |
| moving_obstacle | projection | no | 0.5500 | 0.4140 | 0/1 | local_constraint_projection | no | -0.0068 | no |
| infeasible_constraints | base diagnostic | yes | 0.4865 | 0.0000 | - | disabled_diagnostic | no | 0.0135 | no |
| infeasible_constraints | projection | yes | 0.4865 | 1.2000 | 0/1 | infeasible_conservative_fallback | yes | -0.0135 | no |

## Evaluation correction

The first stress-only execution placed `two_sided_restriction` and
`moving_obstacle` inside an empty one-step feasible set, contrary to the frozen
initial-condition contract that reserves intentional infeasibility for the
labelled infeasible fixture. Before accepting stress results, their positions
were corrected using only derived clearance and one-step `a_max`, `v_max`,
`dt` displacement bounds. No controller, gain, topology, physical parameter or
gate changed. Regression tests now require base collision, successful local
intervention and no fallback in both feasible fixtures. The table and committed
artifacts contain only the corrected evaluation.

These fixtures establish deterministic local projection behavior only. They do
not establish recursive feasibility, unconditional collision avoidance or a
whole-swarm safety theorem.
