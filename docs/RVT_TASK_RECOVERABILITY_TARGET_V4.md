# RVT Task Recoverability Target V4

Schema: `rvt-task-recoverability-target/v4`.

For decision state `x` and candidate `tau in {COMPACT, LINE}`, a matched frozen
counterfactual rollout defines `y_tau(x)=1` only if every replica satisfies:

1. collision-free execution over the complete horizon;
2. no persistent deadlock;
3. valid candidate commitment when transition is required;
4. valid transition execution;
5. required target-topology Metric V3 dwell;
6. downstream mission/goal completion;
7. resolved protocol state without failure;
8. no unresolved safety-projection failure;
9. numerical validity;
10. no irreversible loss of mission progress.

Otherwise `y_tau(x)=0`. Invalid numerical/evaluator rollouts are additionally
flagged invalid and never silently converted into an ordinary negative training
row. The target is centrally generated offline; no rollout outcome is available
to the deployable model.

The pair `(y_COMPACT,y_LINE)` is retained as COMPACT-only, LINE-only,
both-success or both-fail. It is not a winner label, utility threshold,
immediate collision flag, short-horizon formation error, model confidence or
global action-quality score. BOTH_SUCCESS and BOTH_FAIL supervise both
candidates truthfully.
