# Phase 9C-PCA — Transition Protocol Adapter Conformance Audit

Purpose: stop discovering one omitted frozen call per phase. The audit starts
from the frozen `TransitionProtocolNode` class, not from what Phase 9C happens
to call.

## PCA-1/PCA-2 — complete method / call-site matrix

**19 public methods; 13 state-mutating; 16 bound by the publication adapter.**

| frozen method | mutates | adapter | status | frozen source states |
|---|:--:|:--:|---|---|
| `request_intent` | no | yes | BOUND_AND_TESTED | any (returns None if candidate == committed) |
| `adopt_intent` | yes | yes | BOUND_AND_TESTED | `STABLE_TOPOLOGY`, `REARMED`, `COMPLETE` |
| `begin_score_agreement` | yes | yes | BOUND_AND_TESTED | `INTENT_ACTIVE` |
| `accept_score_agreement` | yes | yes | BOUND_AND_TESTED | `CANDIDATE_SCORE_AGREEMENT` |
| `begin_all_ready_agreement` | yes | yes | BOUND_AND_TESTED | `WAITING_FOR_LOCAL_READINESS` |
| `accept_all_ready` | yes | yes | BOUND_AND_TESTED | `ALL_READY_AGREEMENT` |
| `accept_confirmation` | yes | yes | BOUND_AND_TESTED | `TOPOLOGY_CONFIRMATION` |
| `commit` | yes | yes | BOUND_AND_TESTED | `TOPOLOGY_CONFIRMATION` |
| `begin_execution` | yes | yes | BOUND_AND_TESTED | `TOPOLOGY_COMMITTED` |
| `observe_target_tube` | yes | yes | BOUND_AND_TESTED | `TRANSITION_EXECUTION`, `TARGET_DWELL` |
| `mark_complete` | yes | yes | BOUND_AND_TESTED | `TARGET_DWELL` |
| `abort` | yes | yes | BOUND_AND_TESTED | any **except** `COMPLETE`, `REARMED` |
| `try_rearm` | yes | yes | BOUND_AND_TESTED | `ABORTED`, `COMPLETE` |
| `score_message` | no | yes | BOUND_AND_TESTED | requires active lifecycle |
| `readiness_message` | no | yes | BOUND_AND_TESTED | requires active lifecycle |
| `confirmation_message` | no | yes | BOUND_AND_TESTED | requires active lifecycle |
| `status_message` | no | **no** | **DEFECT 13 — see below** | — |
| `_advance` | yes | no | NOT_APPLICABLE (private state setter; correctly never called directly) | — |
| `_require_enabled` | no | no | NOT_APPLICABLE (private guard) | — |

No blank entries.

## Defect 13 (identified, not repaired) — distributed completion agreement

`status_message` is the one public method with no publication call site, and it
is **runtime-required**: the qualified Phase 7R runtime at
`transition_runtime.py:886-901` broadcasts

```python
node.status_message("COMPLETE", "local_target_dwell", now)
```

floods it, and then runs `evaluate_lifecycle_status_agreement(..., "COMPLETE", ...)`
to reach **distributed** completion. The publication adapter instead marks each
node COMPLETE from its own local dwell observation alone, with no distributed
completion agreement.

Same class-A pattern as defects 9, 10, 12: the frozen method exists, the adapter
does not call it. Reported here rather than patched in the same sweep, per
PCA-2.

## PCA-4 — direct state mutation audit

**Zero** direct writes to `state`, `active_intent`, `_score_agreed`, `_all_ready`,
`_confirmed`, `dwell_started_seconds`, `mode_epoch_count`, `abort_cause`,
`rearm_started_seconds` or `local_dwell_complete` anywhere in
`rvt_swarm/phase9c_rb/`. Every lifecycle change goes through a frozen method.
Snapshot restore uses `copy.deepcopy` of the whole object graph, so it never
hand-assigns frozen fields either.

## PCA-5 — precondition conformance

Three adapter guards, all now equal to their frozen counterparts:

| guard | adapter | frozen | verdict |
|---|---|---|---|
| origination | `STABLE_TOPOLOGY`, `REARMED`, `COMPLETE` **and** `active_intent is None` | `adopt_intent` accepts those three states, but internally calls `abort("conflicting_lifecycle")` when an intent is latched — and `abort` raises from `COMPLETE` | conforming |
| retirement | `COMPLETE`, `ABORTED` | `try_rearm` accepts exactly those | conforming |
| abort | skips `STABLE_TOPOLOGY`, `COMPLETE`, `REARMED` | `abort` raises from `COMPLETE`, `REARMED` | conforming (the extra `STABLE_TOPOLOGY` skip is a no-op, nothing to abort) |

The origination guard needed the `active_intent is None` clause: permitting
`COMPLETE` alone let `adopt_intent`'s internal abort fire from a state that
forbids aborting. That was the residual cause of the five xfails.

## PCA-6 / PCA-20 — xfails resolved

All five previously `xfail(strict=True)` transition tests are now ordinary
passing tests. No test was deleted, and the rearm interval was not shortened:
the fixtures and the candidate executor now wait for the frozen
`rearm_inactive_seconds` and let `try_rearm` retire the epoch, as the contract
requires.

## Verified multi-epoch behaviour

Three complete mechanical epochs COMPACT -> LINE -> COMPACT -> LINE with
monotonic `mode_epoch_count` 1/2/3, fresh profile per epoch, no stale agreement
or dwell state, collision-free, and `topology_selection_epoch_count` 0 for
forced diagnostics.
