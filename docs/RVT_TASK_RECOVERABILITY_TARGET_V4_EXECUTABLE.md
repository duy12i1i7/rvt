# RVT Task Recoverability Target V4 Executable Contract

## Total result

Every completed execution maps to exactly one disposition:

- `RECOVERABLE_POSITIVE`, label 1;
- `VALID_TASK_NEGATIVE`, label 0; or
- `GENERATION_INVALID`, no label and no training row.

Evaluation precedence is generation validity, collision, irreversible progress,
deadlock, protocol/commitment, safety/transition, Metric V3 dwell, then goal.
Exceptions become typed `EXECUTOR_EXCEPTION`; no exception implies a label.

## Ten predicates

1. **Collision-free complete horizon.** Robot pairs use the frozen required
   center clearance. Static circles use the frozen radius-aware threshold;
   analytic walls use robot radius plus `0.02 m`; dynamic circles use swept
   relative motion. Each closed control interval minimizes distance under linear
   interpolation. Contact within `1e-9 m` is collision. World-boundary contact is
   also failure.

2. **No persistent deadlock.** Progress is fitted topology-origin displacement
   along the mission axis. Every complete unpaused `3.75 s` window must advance
   at least `spacing_margin=0.05 m`. The deadlock clock pauses and discards its
   partial window during active protocol, readiness wait, transition execution
   and target dwell. Waiting can still fail by horizon; it is not silently called
   motion deadlock.

3. **Candidate commitment valid.** If candidate equals committed topology, this
   is true without an epoch. Otherwise all robot nodes must commit that candidate
   in one lifecycle before horizon, with no partial commitment.

4. **Transition execution valid.** An unchanged candidate holds. A changed
   candidate must use Phase 7 and the frozen profile, enter the candidate Metric
   V3 tube, and avoid abort/timeout. Projection infeasibility remains false until
   a later successful projection resolves it; collision remains latched.

5. **Target Metric V3 dwell complete.** Target is the candidate topology.
   `e_inf <= formation_tolerance_meters` continuously for `3.0 s`; any exit resets
   the physical-time clock.

6. **Downstream goal complete.** Fit the candidate topology origin by
   least-squares role-offset removal. It must remain within formation tolerance
   of `goal_center_meters` for one control period. Metric dwell is independently
   required by predicate 5.

7. **Protocol resolved.** `STABLE_TOPOLOGY`, `COMPLETE` and `REARMED` are success
   states where applicable. `ABORTED`, partial commitment or any active state at
   horizon is failure. A declared F8 assumption violation is a valid task
   negative, not generation invalid.

8. **Safety projection resolved.** Infeasibility or solver failure latches
   unresolved. A finite conservative zero fallback may clear the latch only
   after the next feasible successful projection. Persistent feasible
   intervention alone is not failure.

9. **Numerically valid.** Every state, action, geometry value, queue timestamp
   and metric must be finite and schema-valid. Failure is generation invalid.

10. **No irreversible progress loss.** If longitudinal progress drops by more
    than one nominal spacing from its attained maximum, it must return within one
    spacing margin of that maximum before termination. Temporary delay below this
    condition is not irreversible; horizon goal failure remains an ordinary
    negative.

## Termination vocabulary

Declared causes are `GOAL_COMPLETE`, `HORIZON_COMPLETE`, `COLLISION`,
`PERSISTENT_DEADLOCK`, `PROTOCOL_ABORT`, `PROTOCOL_TIMEOUT`,
`TRANSITION_ABORT`, `TRANSITION_TIMEOUT`, `SAFETY_INFEASIBLE`,
`SAFETY_SOLVER_FAILURE`, `IRREVERSIBLE_PROGRESS_LOSS`,
`WORLD_BOUNDARY_EXIT`, `COMMUNICATION_ASSUMPTION_VIOLATION`,
`INITIALIZATION_INVALID`, `GEOMETRY_INVALID`, `NUMERICAL_INVALID`,
`SCHEDULE_INVALID`, and `EXECUTOR_EXCEPTION`.

Initialization, geometry, schedule, numerical and executor failures are
generation-invalid. A positive requires `GOAL_COMPLETE` and all ten predicates.
Every other generation-valid combination is one valid task-negative. The pure
typed evaluator is `rvt_swarm.phase8e.target.evaluate_target_v4`.
