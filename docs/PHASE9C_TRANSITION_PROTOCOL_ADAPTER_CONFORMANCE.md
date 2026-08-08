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
| `status_message` | no | yes | BOUND_AND_TESTED (defect 13 repaired) | requires active lifecycle |
| `_advance` | yes | no | NOT_APPLICABLE (private state setter; correctly never called directly) | — |
| `_require_enabled` | no | no | NOT_APPLICABLE (private guard) | — |

No blank entries.

## Defect 13 (REPAIRED) — distributed completion agreement

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


---

# Defect 13 repair

## Authoritative completion sequence (D13-1)

Read from `transition_runtime.py:880-918`, in executable order:

1. every node calls `observe_target_tube(local_inside, now)` each step;
2. **only once every node reports `local_dwell_complete`** does the runtime
   proceed -- local dwell is necessary, not sufficient;
3. each node emits `status_message("COMPLETE", "local_target_dwell", now)`
   (exact frozen status and reason tokens, verified from code);
4. those are flooded over the one-hop adjacency for
   `derived.k_confirm_rounds`;
5. `completion_agreement_time = now + k_confirm_rounds * communication_period`;
6. `evaluate_lifecycle_status_agreement(flood, member_ids, intent, "COMPLETE",
   now_seconds=completion_agreement_time, maximum_age_seconds=k_confirm_rounds *
   communication_period + maximum_message_age_seconds)`;
7. on agreement **every** node calls `mark_complete(completion_agreement_time)`;
   on disagreement every node aborts with the agreement's own reason.

## Root cause

The adapter called `node.mark_complete(now)` per robot the instant that robot's
own `observe_target_tube` returned True. Steps 3-6 -- the entire distributed
status path -- were absent, so completion was a local decision.

## Repair

All four frozen calls are now bound in `advance_transition_lifecycle`, in the
authoritative order, using the same range-gated cut-aware adjacency as every
other protocol phase. COMPLETE status messages are therefore subject to the
identical F8 partition, delay, loss and freshness semantics; they are not
special-cased to be reliable. No agreement logic is recreated.

## Measured separation

`train-f1-00`, N=6, S2 forced initialization:

| event | time |
|---|---:|
| all nodes `local_dwell_complete` | 9.45 s |
| distributed status agreement | 10.20 s |
| delta | 0.75 s = `k_confirm_rounds` (5) x `communication_period` (0.15 s) |

`agreed: True`, reason `lifecycle_status_agreed`. The two instants are recorded
separately in `session.completion_agreements` and carried through snapshots, so
the distinction stays visible in later audit records.

## Method matrix, corrected terminology

* total methods audited: **19**
* public runtime methods: **17**
* private helpers intentionally never called directly: **2** (`_advance`,
  `_require_enabled`)
* bound and tested: **17**
* runtime-required omissions remaining: **0**
