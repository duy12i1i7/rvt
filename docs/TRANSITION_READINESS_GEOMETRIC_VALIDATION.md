# Transition Readiness Geometric Validation

Validation is offline and diagnostic.  The simulator may compare the robot-local
certificate with exact fixture geometry, but exact geometry is never passed to
the runtime certificate.

Every robot-step is classified as geometric SAFE/UNSAFE and certificate
SAFE/UNSAFE/UNKNOWN.  Reports are partitioned by role, directed topology pair,
team size, and fixture.  They include false-SAFE, false-UNSAFE, UNKNOWN, and the
delay from first geometric SAFE to first certificate SAFE.

The frozen gate is false-SAFE rate exactly 0 on all Phase 7 qualification
fixtures.  UNKNOWN may delay or abort a transition.  False-UNSAFE is reported
and may not be reduced by tuning against mission success.  Margins and fixtures
are fixed before the transition matrix is run.

## Frozen result

The eight predeclared constriction fixtures produced 48 initial robot-step
certificates:

| outcome | count | rate |
|---|---:|---:|
| false SAFE | 0 | 0.000 |
| false UNSAFE | 0 | 0.000 |
| UNKNOWN | 4 | 0.083 |

All four UNKNOWN records are outer roles in the incomplete-sensing fixture.
Centre-first and one-outer-constrained fixtures return SAFE for unblocked roles
and UNSAFE for every role whose exact offline swept capsule intersects wall
material.  The first geometric-safe and first certificate-SAFE step coincide in
the static open fixtures.  In `all_roles_eventually_ready`, both change on the
predeclared wall-removal step; no success-conditioned timing or margin was used.

The complete per-robot states and margins are in
`results/phase7_transition_protocol/constriction/fixtures.json`.
