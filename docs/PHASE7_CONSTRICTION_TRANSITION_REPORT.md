# Phase 7 Constriction Transition Report

Eight deterministic mechanical fixtures were declared before evaluation.

| fixture | initial all-ready | final all-ready | committed | mode epochs | outcome |
|---|---|---|---|---:|---|
| wider to narrower | yes | yes | yes | 1 | completed protocol mechanics |
| narrower to wider | yes | yes | yes | 1 | completed protocol mechanics |
| centre ready before outer | no | no | no | 0 | readiness timeout |
| one outer wall constrained | no | no | no | 0 | readiness timeout |
| all roles eventually ready | no | yes | yes | 1 | same lifecycle proceeds |
| no feasible transition window | no | no | no | 0 | readiness timeout |
| incomplete local sensing | no | no | no | 0 | four UNKNOWN certificates |
| temporary communication loss | no | yes | yes | 1 | waits, then proceeds after restored contract |

All fixtures remain collision-free.  False-SAFE, false-UNSAFE, premature
commitment, source-to-source epoch, no-op epoch, and partial commitment counts
are all zero.

The historical common-KEEP defect is directly reproduced by `centre ready
before outer`: centre roles 1 and 4 report SAFE, outer roles 0, 2, 3 and 5 report
UNSAFE, all-ready is false, and KEEP is not committed.  `all roles eventually
ready` removes the same predeclared wall constraints, reuses the active
lifecycle without incrementing an epoch, reaches all-ready, confirms, and
creates one mode epoch.

Actual readiness/status traffic ranges from 33,550 to 101,334 bytes per fixture.
Per-robot states, constrained roles, byte counts and geometric classifications
are in `results/phase7_transition_protocol/constriction/fixtures.json`.

P7-G3 and P7-G6 pass.
