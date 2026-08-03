# KEEP Transition Negative Result

## Preserved Evidence

Phase 7 evaluated the complete six-pair matrix with immediate target-role
execution: 47/144 episodes completed target dwell and 144/144 remained
collision-free. KEEP-edge transitions completed 16/96 episodes; the direct
COMPACT/LINE edges completed 31/48. There were 97 emergency aborts after the
local safety projection reported infeasibility, and no infeasible action was
integrated.

The independent Phase 7R oracle reconstructed all 97 failed local projection
calls. Every case was classified `B_independently_infeasible`, with zero
production/oracle mismatches and an explicit irreducible conflicting constraint
set. The result is therefore a confirmed mechanical limitation under the
declared contract, not a serialization or software bug.

Phase 7R applied the one permitted generic smooth role-space execution repair.
The repaired matrix completed 92/144 episodes with 144/144 collision-free.
Both COMPACT/LINE directions completed all 48/48 episodes and all 12/12
pair/team-size cells. KEEP-edge transitions improved to 44/96 episodes but
retained 52 projection-infeasibility aborts.

## KEEP Cell Accounting

Across the 24 KEEP-edge pair/team-size cells after repair:

| directed edge | qualified cells | failed cells |
|---|---:|---:|
| `KEEP -> LINE` | 6/6 | 0/6 |
| `LINE -> KEEP` | 5/6 | 1/6 (`N=5`) |
| `KEEP -> COMPACT` | 0/6 | 6/6 |
| `COMPACT -> KEEP` | 0/6 | 6/6 |
| total | 11/24 | 13/24 |

All 52 remaining aborts lie on KEEP edges: 48 episodes on KEEP/COMPACT and four
`LINE -> KEEP` episodes at `N=5`. Readiness/execution consistency and the
communication contract passed; there was no unsafe partial commitment,
no-op epoch or hidden retry.

## Scope Decision

Safety thresholds were not weakened because they encode the frozen collision
contract and the oracle confirmed true infeasibility. Controller gains,
topology geometry, action bounds, formation tolerance and physical parameters
were not retuned because Phase 7R was the final permitted repair cycle.
Selective KEEP edges by team size were rejected because they would create a
post-hoc cell-specific graph and would not support the declared variable-size
claim.

KEEP remains mechanically valid and reproducible under the forced-topology
runtime. It is retained as an open-space fixed reference, controller
qualification topology, diagnostic candidate, historical comparison and
reported negative result. It is excluded only from primary online transition,
learning and recovery claims.

Raw records remain unchanged in `results/phase7_transition_protocol/` and
`results/phase7_transition_execution_repair/`.
