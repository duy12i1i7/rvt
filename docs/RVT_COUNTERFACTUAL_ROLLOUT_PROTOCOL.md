# RVT Counterfactual Rollout Protocol

Schema: `rvt-counterfactual-rollout/v1`.

COMPACT and LINE start from byte-identical physical state, source lifecycle,
message condition and mission progress. They receive equal horizons and replica
budgets, the frozen controller, local safety projection, transition protocol,
readiness certificate, role-space profile, communication realization, Metric V3
and goal rule. A required topology change follows the generic frozen lifecycle;
an unchanged candidate remains in the source topology without a no-op epoch.

Deterministic families use one replica. F8 and F9 use three matched replicas
with identical disturbance seeds for both candidates. Aggregation is
**all-success**: every valid replica must meet all V4 conditions. Mixed outcomes
set the instability flag; numerical invalidity sets invalid and blocks the row.
Timeout is the family horizon. Abort, unresolved protocol/safety failure,
deadlock or incomplete final dwell is failure.

The candidate receives no privileged future state. The offline evaluator may
inspect complete outcomes after rollout, but saved model inputs remain
robot-local. Every trace records source commit, initial-state hash, lifecycle
hash, communication hash, rollout-config hash, seed, horizon, cost and abort.
The rollout oracle is diagnostic and non-deployable.
