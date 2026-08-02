# Phase 6 Initial-Condition Contract

This contract and its seeds are frozen before closed-loop qualification. It is
mechanical controller evaluation, not scientific scenario-family construction.

## Matrix and seeds

Team sizes are `{5, 6, 8, 12, 16, 24}` and forced topologies are KEEP, COMPACT
and LINE. The predeclared seeds are `{61001, 61002, 61003, 61004, 61005}`.
Every seed is run; there is no resampling after rejection or failure.

For a topology template centered at origin `c` with mission rotation `R`, exact
positions are `p_i = c + R r_i`. Initial velocities are zero unless the fixture
declares velocity perturbation.

| Fixture | Position perturbation | Velocity perturbation | Goal origin |
|---|---|---|---|
| exact topology | zero | zero | initial origin |
| bounded position | independent seeded component bounds of `spacing_margin = 0.05 m` | zero | initial origin |
| bounded velocity | zero | independent seeded component bounds of `v_max * dt = 0.135 m/s` | initial origin |
| combined | both declared bounds | both declared bounds | initial origin |
| open translation | bounded combined initialization | bounded velocity bound | `4 * nominal_spacing = 3.6 m` along mission direction |
| local safety stress | explicitly listed local peer/obstacle geometry | fixture-specific bounded velocity | local progress target |

Open translation is evaluated at mission headings 0 and pi/3. Stabilization
budget is `4 * recovery_dwell = 12 s`; translation budget is the larger of that
budget and `2 * translation_distance / v_max + recovery_dwell = 11 s`, hence
12 s. Dwell is the unchanged 3 s Metric V3 requirement.

## Validity checks

Before each episode the generator checks finite arrays, exact shape, unique
persistent roles, Metric V3 initial error consistent with the requested
fixture, robot-robot center distance strictly above the configured required
clearance, obstacle clearance where applicable and physical initial speed.

A rejected initialization is recorded once with all reasons and is not
replaced. Exact topology generation must reject zero episodes. Perturbed
fixtures are bounded analytically below half the nominal pair separation; any
unexpected collision is an invalid initialization, not a controller failure.

Safety stress fixtures are declared independently of controller output. They
may be intentionally locally infeasible only when labelled as such; infeasible
fixtures are not counted as formation/translation qualification cells.
