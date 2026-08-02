# Phase 6 Forced-Topology Qualification Report

## Scope and provenance

Phase 6 was built from approved Phase 5 commit
`b47a95fe238550e7fb7492c6fafd8427c1b572ec`. It adds one authoritative
robot-local forced-topology stack and does not replace or activate the existing
decentralized selection runtime. The Phase 5 model stayed inactive; no learned
output, residual, online transition, readiness mechanism, consensus, training,
scientific label generation or final-test layout entered an action or result.

The frozen qualification contains 540 unique episodes: 360 stabilization and
180 open translation. Team sizes are `{5,6,8,12,16,24}`, topologies are KEEP
0, COMPACT 5 and LINE 2, seeds are `{61001..61005}`, and translation headings
are 0 and pi/3. All initial conditions were accepted without resampling.

## Authoritative local stack

For observer i and fixed topology tau, the controller uses only immutable own
state and role, one local registry slice, fresh one-hop messages, local obstacle
primitives, the shared static topology-origin goal and immutable configuration:

`e_ij = (p_j - p_i) - R(psi) d_ij^tau`

`u_form = a_max k_form mean(e_ij / spacing)`

`p_i_goal = p_goal_origin + R(psi) r_i^tau`

`u_goal = a_max k_goal ball_clip((p_i_goal - p_i) / spacing, 1)`

`u_damp = -a_max k_damp v_i / v_max`

The derived local obstacle term and these three terms form `u_base`. Option B,
an exact two-dimensional per-robot convex projection, minimizes
`||u_i-u_base||^2` over only robot i's acceleration disk and locally derived
peer/obstacle half-spaces. It uses deterministic active-set enumeration, not a
joint optimizer. Empty feasible sets return an explicit bounded maximum-away
fallback; malformed/nonfinite input fails closed and is logged.

The action is world-frame acceleration in m/s^2. Execution norm-clips at 0.6
m/s^2, applies `v[k+1]=clip(v[k]+u[k]dt, 0.9 m/s)`, then
`p[k+1]=p[k]+v[k+1]dt` with `dt=0.15 s`. This semi-implicit Euler contract is
consistent with the unchanged Phase 5 residual units. There is no action delay.

## Cell qualification

Every listed N/topology combination passed all four stabilization fixtures and
both translation headings. `SE` and `TE` are worst final Metric V3 errors;
`TG` is worst final goal-origin error. Stabilization has 20 and translation has
10 episodes per row. All rows have collision-free, dwell and translation-goal
rates 1.00 and deadlock rate 0.00. There are no rejected cells.

| N | Topology | Stabilization | SE (m) | S dmin (m) | Translation | TE (m) | TG (m) | T dmin (m) | T saturation (%) |
|---:|---|---|---:|---:|---|---:|---:|---:|---:|
| 5 | KEEP | qualified | 0.0017 | 0.8143 | qualified | 0.0025 | 0.0774 | 0.7702 | 1.02 |
| 5 | COMPACT | qualified | 0.0019 | 0.7632 | qualified | 0.0023 | 0.0779 | 0.7187 | 1.05 |
| 5 | LINE | qualified | 0.0020 | 0.8058 | qualified | 0.0037 | 0.0783 | 0.7712 | 1.00 |
| 6 | KEEP | qualified | 0.0018 | 0.8048 | qualified | 0.0016 | 0.0770 | 0.7735 | 1.08 |
| 6 | COMPACT | qualified | 0.0018 | 0.7933 | qualified | 0.0022 | 0.0766 | 0.7624 | 1.02 |
| 6 | LINE | qualified | 0.0019 | 0.7910 | qualified | 0.0052 | 0.0770 | 0.7617 | 1.12 |
| 8 | KEEP | qualified | 0.0022 | 0.7394 | qualified | 0.0032 | 0.0764 | 0.6923 | 0.95 |
| 8 | COMPACT | qualified | 0.0020 | 0.7699 | qualified | 0.0041 | 0.0768 | 0.7264 | 0.86 |
| 8 | LINE | qualified | 0.0023 | 0.7709 | qualified | 0.0043 | 0.0762 | 0.7266 | 1.02 |
| 12 | KEEP | qualified | 0.0026 | 0.7513 | qualified | 0.0040 | 0.0761 | 0.7132 | 0.93 |
| 12 | COMPACT | qualified | 0.0021 | 0.7458 | qualified | 0.0088 | 0.0756 | 0.7236 | 0.86 |
| 12 | LINE | qualified | 0.0021 | 0.7767 | qualified | 0.0075 | 0.0760 | 0.7464 | 0.95 |
| 16 | KEEP | qualified | 0.0034 | 0.7670 | qualified | 0.0066 | 0.0753 | 0.7201 | 0.84 |
| 16 | COMPACT | qualified | 0.0026 | 0.7652 | qualified | 0.0077 | 0.0748 | 0.7182 | 0.81 |
| 16 | LINE | qualified | 0.0023 | 0.7821 | qualified | 0.0083 | 0.0749 | 0.7443 | 0.83 |
| 24 | KEEP | qualified | 0.0030 | 0.7786 | qualified | 0.0077 | 0.0761 | 0.7417 | 1.05 |
| 24 | COMPACT | qualified | 0.0022 | 0.7681 | qualified | 0.0067 | 0.0757 | 0.6768 | 1.02 |
| 24 | LINE | qualified | 0.0022 | 0.7807 | qualified | 0.0080 | 0.0757 | 0.7200 | 1.01 |

The full 72 stabilization cells and 36 heading-specific translation cells are
reported separately in the companion reports and machine-readable summaries.

## COMPACT findings

- COMPACT uses the shared pairwise controller and gains. Its registry-local
  formation degree is 1-3 at N=5 and 2-3 at all declared even team sizes; max
  nominal degree 3 was sufficient throughout this matrix.
- Odd N=5 and even N through 24 all achieved 1.00 stabilization, translation,
  collision-free and dwell rates.
- Metric V3 is the maximum per-robot role error, so the reported worst final
  COMPACT errors of 0.0026 m in stabilization and 0.0088 m in translation bound
  both outer and inner roles; there is no unresolved systematic role failure.
- Every COMPACT episode maintained the final tube continuously for the 3 s
  dwell. No gate-relevant two-column oscillation developed. The retained
  episode artifact does not support a stronger spectral claim about motion
  below the Metric V3 tolerance.
- Stabilization saturation was zero. Translation saturation was
  `{1.05,1.02,0.86,0.86,0.81,1.02}%` for increasing N, so it did not grow
  systematically with team size.
- The obstacle response is topology-independent by contract and passes the
  same deterministic test for KEEP, COMPACT and LINE. Phase 6 did not create a
  COMPACT-specific obstacle course.

## Safety and locality

Controller-invocation spies and intervention tests hold robot i's accepted
local input fixed while changing out-of-range robots, unobserved obstacles,
global centroid/error, robot-array order and evaluation metadata. Formation,
goal, obstacle, base and projected actions remain unchanged. Positive controls
for fresh peers, local obstacles and forced topology change the expected term.
Sequential, reordered, parallel and mixed-N calls remain isolated.

Safety tests verify unchanged safe actions, physical bounds, close peer and
obstacle intervention, stale-data inflation, ordering/translation/rotation
consistency, finite output, one-action decision variables and explicit
fallback/failure. In stress evaluation, feasible two-sided and moving hazards
were mitigated at 0.55 m; the deliberately infeasible fixture correctly
reported fallback and remained unsafe. This is empirical local collision
mitigation, not formal whole-swarm safety.

## Gate results

| Gate | Result | Evidence |
|---|---|---|
| P6-G1 locality | pass | zero strict-runtime violations; no joint-state input, centroid/error control or centralized action computation |
| P6-G2 numerical validity | pass | 540/540 finite episodes; zero solver failure/infeasibility in closed loop; bounded two-dimensional actions |
| P6-G3 exact initialization | pass | all 18 N/topology cells: CF 1.00, dwell 1.00, no deadlock |
| P6-G4 bounded perturbation | pass | all 54 bounded fixture cells: CF 1.00, dwell 1.00 across all five seeds |
| P6-G5 open translation | pass | all 36 heading cells: CF, goal and dwell 1.00; no deadlock |
| P6-G6 safety projection | pass | safe action unchanged; all hazards intervene/fallback; no joint or silent unsafe fallback |
| P6-G7 COMPACT | pass | same gates and controller as KEEP/LINE through N=24 |
| P6-G8 variable size | pass | all 18 N/topology combinations separately reported; zero rejected |
| P6-G9 latency | pass | N=24 bounded median 5.498 ms and p95 7.664 ms versus 150 ms period |
| P6-G10 preservation | pass | model inactive; no learned action, transition, readiness or selection protocol |

Central simulator aggregate latency reaches 328.064 ms at N=24 and is reported
separately. The deployable adapter consumes already received messages and does
not scan joint state. Range-bounded one-hop degree nevertheless grows from 4 to
16 in the declared formations, and the exact projection has O(m^3) worst-case
implementation cost for m local constraints.

## Verification

The approved Phase 5 baseline reports `1329 passed, 1 warning`. The Phase 6
working-tree suite reports `1471 passed, 1 warning`, adding 142 required and
supporting tests. The 14 specifically required Phase 6 files pass `142/142`.
The focused strict-decentralization, no-global-controller, no-joint-optimizer,
no-magic-number, locality, action-semantics and safety set passes `67/67`.
The single warning is the pre-existing tensor-to-scalar warning in
`test_simplified_model.py`.

## Corrections and historical impact

The new forced-topology stack affects only the new Phase 6 diagnostic path;
existing runtime decisions and historical results are unchanged. Two
evaluation-only defects were corrected before acceptance: the script import
path now resolves the repository package when launched directly, and two
stress fixtures were moved from accidentally infeasible geometry to feasible
derived one-step geometry. A duplicate N=24/one-obstacle timing cell was also
removed. None changed controller behavior, gains, topology geometry, physical
configuration, Metric V3 or a predeclared gate.

Phase 6 adds mechanical evidence only. It does not retroactively validate any
historical learned or transition result.

## Phase 7 blockers

- Recoverability and residual heads remain scientifically untrained and
  inactive.
- No learned topology selection, transition-readiness certificate, consensus
  or generic transition protocol exists.
- Local projection has no recursive or whole-swarm safety proof and can be
  infeasible under locally impossible geometry.
- Central simulator neighbour discovery remains global infrastructure; the
  deployable transport must supply one-hop messages without a joint-state scan.
- Mechanical qualification stops at N=24 and at the declared open-space and
  one-step stress fixtures. It is not final-scenario evidence.

## Verdict

**D. KEEP, COMPACT and LINE are mechanically valid under the robot-local
controller and safety stack through the declared scope; proceed to Phase 7.**
