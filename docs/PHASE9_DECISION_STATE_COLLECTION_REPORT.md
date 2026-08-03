# Phase 9 Decision-State Collection Report

## Frozen Schedule

The job manifest materializes all 15,300 slots using only the frozen schedules:

- five-slot episodes: `0.10, 0.30, 0.50, 0.70, 0.90`;
- four-slot episodes: `0.15, 0.40, 0.65, 0.90`;
- control step: `ceil(normalized_time * horizon / dt)`.

Each planned event references its source episode, study, split, family, layout
hash, team size, source class, both candidates, replica count and all approved
protocol hashes. Identity and ordering tests pass.

## Actual Collection

No source episode reached simulator step 0, so no source-state hash, lifecycle
state, source topology or robot-local ego-graph fingerprint was materialized.

| item | count |
|---|---:|
| planned slots | 15,300 |
| available events | 0 |
| unavailable events caused by early termination | 0 |
| availability not evaluated | 15,300 |
| materialized decision events | 0 |

The 15,300 slots remain in the denominator. They are not reported as
unavailable because source execution never established their availability.

