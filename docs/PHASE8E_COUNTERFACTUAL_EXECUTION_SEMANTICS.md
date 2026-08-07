# Phase 8E Counterfactual Execution Semantics

## Snapshot and injection

The rollout starts after the source control step at the resolved Phase 9B event
timestamp. Snapshot includes simulator time/index, robot position/velocity/
acceleration, persistent roles, committed topology, transition profile,
independent protocol nodes, controller state, safety latches, message queues and
timestamps, communication schedule, disturbance counters, dynamic obstacle
state, mission progress and event state.

Create two independent deep clones. Their canonical hashes must be byte-identical
before candidate injection. Mutation isolation is mandatory. Candidate injection
occurs at the same next communication tick.

## Candidate behavior

- Candidate equals current topology: hold or continue the candidate; create no
  source-equals-target epoch and evaluate the complete remaining mission.
- Candidate differs while protocol is stable: originate through Phase 7 and
  require intent, score, readiness, all-ready, confirmation, profile and dwell.
- Candidate equals an already active lifecycle target: continue that lifecycle.
- Candidate differs from an active target: never supersede the lifecycle. Let it
  complete or abort, wait for frozen rearm, then request the candidate if horizon
  remains. Failure to do so before horizon is a valid negative.

The source lifecycle is never reset to make a candidate easier.

## Horizon, replicas and matching

Rollout horizon is the remaining time to the absolute family episode horizon.
That same remaining horizon is candidate and mission timeout; there is no hidden
extra timeout. F8 and F9 use three replicas per candidate; other families use
one. Aggregation is all-success.

For every paired replica, initial snapshot, source lifecycle, remaining horizon,
runtime config, communication schedule identity, matched disturbance seed and
dynamic-obstacle snapshot/seed must match. Counter-key streams are independent
objects with identical keys. Physical range edges may diverge after candidate
motion; random schedules may not.

Any initial hash, lifecycle, horizon or stream mismatch makes the pair
generation-invalid. It emits no training row and is never replaced. Diagnostic
headroom is not read. Candidate outcomes are visible only to the offline Target
V4 evaluator after execution and never to source policy or robot-local inputs.

Rejected alternatives were direct mode assignment for changed candidates,
aborting an active source lifecycle for convenience, restarting the mission
clock, candidate-specific disturbances, and source-equals-target no-op epochs.
