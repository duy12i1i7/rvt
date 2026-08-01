# Post-Parameter-Repair Failure Attribution

This attribution covers all failures of the corrected parameterized V3 runtime
over the complete frozen three-cell set: 3 alpha cells x 2 geometry variants x
5 seeds. Exactly one primary A-J category is assigned to each failed episode.

## Classification Result

| category | count |
|:---:|---:|
| A | 0 |
| **B** | **16** |
| C | 0 |
| D | 0 |
| E | 0 |
| F | 0 |
| G | 0 |
| H | 0 |
| I | 0 |
| J | 0 |

The 16 failures are all 10 alpha 0.25 episodes and 6 alpha 0.35 episodes. Alpha
0.45 has no remaining failed episode.

## Primary Cause: B

**Outer-role expansion begins while wall material remains inside its derived
future expansion region.**

The corrected runtime makes KEEP -> LINE at step 30 and LINE -> KEEP at step 42
in every episode. Centre roles 1 and 4 have a correct 0.55 m detector, see their
own band open, satisfy the 3-step evidence rule when the commitment lock releases,
and originate recovery. Trigger propagation and confirmation then commit KEEP
for the entire communication component in the same control step.

At step 42, every failed episode has outer roles among robots 0, 2, 3, and 5
with wall returns still present in their correct 1.45 m forward sector. The
commit nevertheless changes all robots to KEEP, beginning the expansion control
mode while those outer robots remain locally constrained. Their measured
immediate lateral velocities range from -0.216 to 0.133 m/s; the sign varies
with transient formation error, but the common KEEP commitment is already in
force and the controller has begun the reconfiguration.

No failed episode has a communication disagreement, partial commitment, invalid
initial condition, collision, or evaluator inconsistency. All remain
collision-free, but they fail to cross and therefore do not reach the goal or
complete KEEP dwell.

## Why This Is Not Category A

The role-dependent detector is geometrically correct for each robot: its sector
covers the complete role-specific prospective expansion band plus clearance and
all widths are observable under `R_obs`. The recovery originators are locally
safe according to their own centre-role geometry. The defect is that their local
evidence authorizes a simultaneous KEEP commitment for outer roles whose own
correct detectors still report wall material.

## Architectural Consequence

This satisfies the predeclared CASE 2 mechanism. A two-phase distributed
safe-expansion certificate is scientifically justified as the next architectural
step: all participating roles must certify their local expansion region before a
common KEEP commitment. No such protocol was implemented in this task.

Per-episode evidence is in
`results/post_parameter_repair_regression/failure_attribution.json`.
