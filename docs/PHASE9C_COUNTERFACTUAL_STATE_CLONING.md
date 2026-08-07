# Phase 9C Counterfactual State Cloning (RB-7, RB-8, RB-9, RB-13, RB-14)

## Snapshot design

Two artefacts, because they answer different questions:

* `canonical_execution_state(session)` enumerates every execution-relevant
  mutable field as plain JSON. It is what gets hashed and compared, and its
  explicitness is what makes coverage **auditable**.
* `EpisodeSnapshot` additionally carries a deep copy of the live session. That
  is what `restore()` returns, and it is what guarantees **completeness** —
  nothing can be forgotten, because the whole object graph is copied.

Either alone is insufficient: the canonical dict risks a silently omitted
field, the deep copy alone makes coverage unauditable. Both are kept, and
`test_the_deep_copy_and_the_canonical_dict_agree` checks they never drift.

Nine top-level sections: `simulator`, `robots`, `communication`,
`dynamic_obstacles`, `disturbance`, `seed_streams`, `mission_and_evaluator`,
`source_policy`, `event_log`. Per robot: pose, velocity, acceleration,
committed topology, both role offsets, transition progress, the three safety
latches, projection-intervention count, policy state, the full Phase 7 node
(state, epoch, abort cause, active intent with token hash) and the neighbour
table with message timestamps. Source-policy state covers S0 consumed ordinals
and dispositions, S3 and S4 evidence hysteresis, and S5 perturbation state.
Evaluator state covers progress maxima, irreversible-loss flag, both deadlock
window fields and the per-topology Metric V3 dwell clocks.

## Why there is no RNG state to restore

Every stream is a `CounterStream`, a frozen `(seed, process)` pair with draws
taken at explicit counter coordinates. There is no mutable RNG object anywhere,
so snapshot/restore is exact by construction, two clones from one snapshot draw
identical exogenous realizations without sharing state, and **neither candidate
can advance the other's stream** — `test_one_candidate_cannot_advance_the_other_stream`
burns fifty draws on one clone and shows the sibling is unaffected.

## Exogenous versus endogenous

Matched: the counter-keyed disturbance draws, the F8 delay/drop/cut schedule,
and the F9 trajectory process and seed identity. Free to diverge: robot
trajectories, local observations, message payloads and recipients — the
communication graph is range-gated, so candidate motion legitimately changes who
hears whom. That is treatment response, not unmatched randomness.

## Candidate executor

* **Case A**, candidate equals the committed topology: hold and continue. No
  request is issued, so no source-equals-target lifecycle exists.
* **Case B**, candidate differs: the request goes through the real Phase 7
  protocol. Nothing commits a topology centrally.

The source policy is replaced by an inert base policy inside a counterfactual so
it cannot keep originating scripted events during the rollout.

F8 and F9 run three replicas, every trace retained individually; all other
families run one. `all_success` is applied only afterwards, and a single
`GENERATION_INVALID` replica voids the aggregate label rather than being
averaged away.

## Target V4 runtime evaluator

Polarity is the point. Collision, deadlock, protocol abort, transition timeout,
safety infeasibility, solver failure, world-boundary exit, communication
assumption violation and irreversible progress loss are all predicate failures
on a generation-valid record, so they become **valid task-negatives**. Only
`INITIALIZATION_INVALID`, `GEOMETRY_INVALID`, `NUMERICAL_INVALID`,
`SCHEDULE_INVALID` and `EXECUTOR_EXCEPTION` are generation-invalid.

`SAFETY_INFEASIBLE` and `SAFETY_SOLVER_FAILURE` share the frozen disposition but
are never merged: the replica record carries `safety_infeasible_robots` and
`safety_solver_failure_robots` as separate counters.
