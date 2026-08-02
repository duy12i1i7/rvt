# RVT Transition State Machine

Each robot owns an independent state object and one committed topology.

`STABLE_TOPOLOGY -> INTENT_ACTIVE -> CANDIDATE_SCORE_AGREEMENT ->
WAITING_FOR_LOCAL_READINESS -> ALL_READY_AGREEMENT ->
TOPOLOGY_CONFIRMATION -> TOPOLOGY_COMMITTED -> TRANSITION_EXECUTION ->
TARGET_DWELL -> COMPLETE -> REARMED`.

Topology remains the source through intent, score, readiness, all-ready, and
confirmation.  Exactly one mode epoch is added at `TOPOLOGY_COMMITTED`.
Readiness waiting, duplicate messages, retries, and rejected no-op requests do
not add epochs.

Active precommit states can abort for invalid/stale intent, lifecycle conflict,
source mismatch, communication timeout, score disagreement, readiness timeout,
persistent UNKNOWN, confirmation failure, graph-contract violation, malformed
message, or invalid target.  These retain the source.  Execution/dwell can
emergency-abort for persistent safety projection failure, infeasible fallback,
collision, or numerical failure; the target remains recorded as committed and
the lifecycle records the emergency cause rather than silently reversing.

A newer valid lifecycle supersedes only STABLE, COMPLETE, REARMED, or an
explicitly closed aborted lifecycle.  It never replaces an active committed
transition.  Rearm requires the configured physical inactive time, stable
topology, and no conflict.

Runtime completion uses exchanged local target-stability statuses.  The frozen
Metric V3 target tube and configured dwell are independently required by the
offline qualification evaluator; its centroid is never a runtime input.
