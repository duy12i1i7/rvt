# Phase 9 Initialization Validation Report

## Status

`FAIL_FATAL_EXECUTION_BINDING`

The Phase 8 and Phase 9B provenance preflight passed 24/24 checks. The
authoritative manifest contains 3,120 source-episode slots and no final-test
job. Study A train and checkpoint-selection validation exclude N=24; the 60
Study A N=24 source jobs are marked sealed.

The first canonical nonsealed source job failed before simulator step 0. The
Phase 8 `ScenarioLayout` exposes `start_center_meters`, `goal_center_meters`,
canonical obstacle primitives and dynamic paths. The only full decentralized
closed-loop harness passes that object to a legacy environment that requires
`start_center`, `goal` and `obstacle_array`.

No episode initialization was accepted or rejected under scientific task
semantics. Counts are therefore:

| item | count |
|---|---:|
| planned source episodes | 3,120 |
| unique source jobs whose runtime binding was attempted | 1 |
| infrastructure attempts including the permitted retry | 2 |
| initialized scientific episodes | 0 |
| simulator steps | 0 |
| deterministic task initialization rejections | 0 |

The failure is an implementation-boundary failure, not an invalid initial
condition and not a task collision. No replacement episode or seed was used.

