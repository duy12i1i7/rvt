# RVT-FD24 Scenario Headroom Protocol

Every layout/team-size cell is assigned by frozen diagnostic policies before
model training:

- **COMPACT_ONLY_SUCCESS:** always COMPACT succeeds and always LINE fails.
- **LINE_ONLY_SUCCESS:** always LINE succeeds and always COMPACT fails.
- **BOTH_SUCCESS:** both fixed candidates satisfy the complete task.
- **BOTH_FAIL:** both fixed candidates fail the complete task.
- **RECONFIGURATION_REQUIRED:** neither fixed policy completes the whole task but the frozen scripted COMPACT/LINE oracle succeeds.
- **INVALID_OR_AMBIGUOUS:** physical, evaluator or stability qualification is invalid.

Success means the complete task-level recoverability conditions, not immediate
clearance. Diagnostic runs use matched initial states and disturbances. A cell
is stable when deterministic reruns agree, or when stochastic replicas produce
the same category under the predeclared all-success aggregation. Unstable cells
are retained as INVALID_OR_AMBIGUOUS with raw outcomes and reasons.

BOTH_SUCCESS and BOTH_FAIL retain both candidate labels; neither becomes an
arbitrary winner. Difficult cells cannot be excluded because a future model
fails. Failed qualification cells and invalid reasons are published. Category
assignment is recomputed only for a versioned geometry/controller/protocol
contract change, which Phase 8 forbids.

The split manifests report diagnostic category by layout and team size. The
Phase 8 tiny audit samples F1, F2, F6 and F10 from train and validation to cover
both-success, LINE-only, COMPACT-only and both-fail target paths. It validates
target plumbing only and is not the full headroom qualification dataset.
