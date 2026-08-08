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

---

# Remaining PCA gates — status

## PCA-18 — Target V4 current-epoch isolation: **PASS**

Seven regressions, all passing:

* epoch 1's LINE commit does **not** satisfy a COMPACT candidate's
  `candidate_commitment_valid`;
* epoch 1's LINE Metric V3 dwell does **not** contribute to COMPACT dwell
  (`metric_v3_dwell[COMPACT] == 0.0` while `metric_v3_dwell[LINE] > 0`);
* checkpoints A (intent adopted) and B (committed, profile active) leave the
  transition predicate false;
* epoch 2 records its **own** distributed completion agreement, with a distinct
  lifecycle id, distinct epoch id and a strictly later agreement time;
* PCA-18E: cumulative task history is *not* over-reset -- longitudinal progress,
  collision history, irreversible-loss and numeric validity all persist across
  the epoch boundary, since the isolation applies to transition-epoch predicates
  only.

## PCA-16 — four-epoch stress: **three epochs verified, fourth bounded by mission end**

Three complete changed-topology epochs run with the full path each time, each
retiring through the frozen rearm and each recording its **own** distributed
completion agreement:

| epoch | transition | local dwell | status agreement | agreed |
|---:|---|---:|---:|---|
| 1 | COMPACT -> LINE (S2 forced) | 9.45 s | 10.20 s | yes |
| 2 | LINE -> COMPACT | 24.60 s | 25.35 s | yes |
| 3 | COMPACT -> LINE | 41.10 s | 41.85 s | yes |

Distinct lifecycle ids, distinct epoch ids, strictly increasing agreement times,
`mode_epoch_count` monotonic 1/2/3, collision-free.

A **fourth** epoch does not fit: the mission reaches `GOAL_COMPLETE` first.
Measured on `train-f1-00` (3 epochs then goal) and `train-f7-00` (3 epochs, goal
at 45.9 s of a 110 s horizon). Each epoch costs roughly 15 s because mission
staging suppresses the goal term throughout, so four epochs exceed the time any
frozen layout leaves before completion. That is the mission ending, not a
protocol defect -- the third epoch completes normally in both cases. Recorded by
test rather than worked around with a synthetic longer mission.

## PCA-8 and PCA-15 — not run

Message epoch isolation beyond the COMPLETE-status path (PCA-8A-8F) and the real
frozen timeout path (PCA-15) were not exercised. They remain the outstanding
conformance gates, and v6 should not run before them: a timeout or stale-message
defect would be silently encoded into 150 headroom classifications, exactly as
happened with v3, v4 and v5.

---

# PCA-8 and PCA-16 — results

## PCA-16 — four-epoch stress: **PASS** (test-only harness)

`tests/test_phase9c_four_epoch_transition_stress.py`.

Four complete changed-topology mechanical epochs:

| epoch | transition | `mode_epoch_count` | committed after |
|---:|---|---:|---|
| 1 | COMPACT -> LINE (S2 forced) | 1 | LINE |
| 2 | LINE -> COMPACT | 2 | COMPACT |
| 3 | COMPACT -> LINE | 3 | LINE |
| 4 | LINE -> COMPACT | 4 | COMPACT |

Four distributed completion agreements, all `agreed`, with four distinct
lifecycle ids, four distinct epoch ids and strictly increasing agreement times,
each strictly later than its own local-dwell instant. After every rearm all
nodes show `active_intent is None`, `_score_agreed`/`_all_ready`/`_confirmed`
false, `dwell_started_seconds is None`, `local_dwell_complete` false and a
retired transition executor. Collision-free.

**Why the scientific fixtures reached only three epochs.** Nothing in the
protocol: the mission reaches `GOAL_COMPLETE` first. Mission staging suppresses
the goal term for roughly 15 s per epoch, so three epochs consume ~42 s and the
team arrives before a fourth can start (`train-f1-00`; `train-f7-00` at 45.9 s
of a 110 s horizon).

**PCA-16A provenance.** The harness pushes the goal *reference* 500 m along the
mission axis and raises only its own horizon (approach C). It is asserted by
test to differ from the compiled scientific goal and horizon. It is not evidence
that any F1-F10 mission contains four transitions; scientific event counts are
unchanged; it enters no split, job manifest, dataset, headroom count or paper
result.

## PCA-8 — message epoch and freshness isolation: **PASS**

`tests/test_phase9c_message_epoch_isolation.py`.

The isolation is structural: the adapter keeps no cross-step agreement-message
queue. **That claim is only valid because the frozen transport is round-local**
-- see the PCA-8R audit below, which establishes the classification from the
frozen code rather than from the adapter. Every phase builds its messages
fresh from the nodes' current lifecycle state and floods them synchronously over
the current adjacency, so no cross-epoch message reservoir exists. Asserted by
test, along with the absence of any manual queue purging.

The frozen validator is exercised directly with genuinely constructed messages:

| case | result |
|---|---|
| 8A score message from a previous epoch | rejected by `validate_message_context` |
| 8B readiness from a previous epoch | rejected |
| 8C confirmation from a previous epoch | rejected |
| 8D COMPLETE status from a previous epoch | rejected |
| 8E same-epoch message beyond `maximum_message_age_seconds` | rejected |
| fresh same-epoch message | **accepted** (non-vacuity) |
| 8F duplicate request for the committed topology | refused; no second agreement, no epoch increment |
| 8G F8 transport | every phase, COMPLETE status included, floods over the same range-gated cut-aware adjacency -- no reliable bypass |

The frozen freshness bound is not duplicated anywhere in the adapter (asserted:
the literal `0.45` does not appear).

## PCA-15 — not run

The real frozen timeout path was not exercised. It is the one remaining
conformance gate, and v6 was not generated.


---

# PCA-8R — transport semantics audit

The earlier PCA-8 entry justified "no cross-step queue" from the publication
adapter and called it "stronger isolation". That was the wrong direction of
evidence, and the phrasing pre-judged the question. Classification is now taken
from the frozen implementation.

## Classification: **ROUND_LOCAL**

Authoritative implementation:
`transition_protocol.flood_transition_messages`.

| property | frozen behaviour |
|---|---|
| documented contract | "Flood immutable original records; the simulator performs delivery only" |
| message store | `stores` is constructed **inside** the call, one dict per member |
| persistence | none -- no `self.`, no module state; the call returns a `FloodResult` |
| carried object | only the optional `TransitionByteLedger`, an accounting record |
| enqueue / delivery | both occur within the single flood, across `rounds` hops |
| delay units | protocol **rounds**, not control steps |
| loss / partition | expressed as adjacency: a round-local graph, or a per-round `Sequence[Mapping]` schedule |
| time variation | `temporary_disconnection_schedule(adjacency, rounds)` returns a per-round schedule consumed **within one flood** |
| lifecycle vs ordinary messages | identical mechanism; lifecycle status messages use the same flood |

No lifecycle message can survive into a later control step, because the frozen
transport provides no mechanism for it to do so.

## Consequence: **Defect 14 does not exist**

The absence of a cross-step lifecycle delay queue in Phase 9C is **conformance**,
not an omission. Binding a persistent queue for lifecycle messages would have
*added* semantics the frozen protocol does not have.

PCA-8R3 (real delayed old-epoch delivery through the transport) is therefore not
constructible, and PCA-8R4's alternative applies: the frozen contract models
lifecycle-message disruption as loss/partition via adjacency, **not** as
persistent delivery delay. Reported explicitly rather than manufacturing a delay
the contract does not contain.

## What the adapter must therefore match, and does

* all five agreement phases -- intent, score, all-ready, confirmation and
  COMPLETE status -- use the frozen flood (asserted by test);
* no lifecycle message is placed in the delayed state-broadcast channel
  (`channel.send(` does not appear in `protocol_session`);
* the only persistent queue in the session carries `state_broadcast` messages,
  a separate frozen concern (peer state under F8 delay/loss), verified by
  inspecting the live queue;
* the F8 cut gates the same adjacency the flood consumes, so there is no
  reliable bypass;
* the frozen F8 contract expresses the cut in whole communication ticks
  (`start_tick`, `duration_ticks`), so it is constant across the rounds of any
  one control step's flood -- consistent with passing a single Mapping.

## PCA-8 final verdict: **PASS**

Transport classification matches, epoch isolation holds at the transport layer
by construction, F8 introduces no reliable bypass, and the message-validator
tests (previous-epoch score/readiness/confirmation/COMPLETE, same-epoch
over-age, fresh-accepted non-vacuity, duplicate refusal) remain in place.

## PCA-15 — still not run

The real frozen timeout path remains the one outstanding conformance gate. v6
was not generated.

---

# PCA-15 — Frozen Timeout Contract

## PCA-15.0 — what the frozen timeout actually is

**`TransitionProtocolNode` has no timeout method and no deadline config field.**
Verified by test: no method name and no `protocol` config field contains
`timeout` or `deadline`.

The two timeout constructs in the qualified runtime are outer-loop labels, not
protocol deadlines:

| site | construct | meaning |
|---|---|---|
| `transition_runtime.py:657` | `"readiness_timeout:" + readiness_result.reason` | a *label* on a failed readiness agreement |
| `transition_runtime.py:926` | `abort = "transition_or_dwell_timeout"` | assigned when `dwell_completion is None` after the episode step budget is exhausted |

There is consequently **no runtime-required frozen timeout method for the
adapter to bind**, and no class-A omission. PCA-15.1 finds nothing missing.

## The publication equivalent

The episode horizon plays the role of the step budget. A lifecycle still active
when the horizon is reached fails Target V4's `protocol_resolved` predicate
through its own frozen failure state:

```
conditions.protocol_resolved.failure_states =
    ["ABORTED", "active_state_at_horizon", "partial_commitment"]
```

## PCA-15.5 — observed trace

Fixture: `train-f1-00`, N=6, RUNTIME_CONFORMANCE_ONLY (only the harness horizon
is shortened; the scientific horizon remains 90.0 s and is asserted intact).

| item | value |
|---|---|
| request accepted | yes, through `request_candidate` |
| states visited | `CANDIDATE_SCORE_AGREEMENT`, `ALL_READY_AGREEMENT` |
| final lifecycle state | `ALL_READY_AGREEMENT` (genuinely still active) |
| `active_intent` at horizon | held by every robot |
| termination | `HORIZON_COMPLETE` at t = 3.30 s |
| distributed completion agreements | none |

No state was mutated to produce this; the lifecycle simply ran out of horizon.

## PCA-15.6 — Target V4 mapping

```
lifecycle active at horizon
  -> protocol_resolved = False   (frozen failure state active_state_at_horizon)
  -> VALID_TASK_NEGATIVE, label 0
```

`executor_completed`, `geometry_valid`, `schedule_conformant` and
`numerically_valid` all remain **true** -- the timeout is a scientific method
failure, never generation invalidity. This mapping is used unchanged in any
later sweep.

## PCA-15.7 — no stale success leaks

`candidate_commitment_valid`, `transition_execution_valid` and
`target_metric_v3_dwell_complete` are all false, and no distributed completion
agreement is recorded. PCA-18 isolation holds under the timeout path.

## PCA-15.10 / 15.11 — reproduction and boundary

Snapshotting before the horizon and replaying reproduces the canonical execution
hash at every step, and the same termination cause, termination time and Target
V4 disposition. With a generous harness horizon the *same* lifecycle completes
and records its distributed agreement -- confirming the timeout is the horizon,
not a protocol defect.

## PCA-15 verdict: **PASS**

## Final conformance matrix

| metric | value |
|---|---:|
| TOTAL_METHODS_AUDITED | 19 |
| PUBLIC_METHODS | 17 |
| PRIVATE_HELPERS | 2 |
| BOUND_AND_TESTED | 17 |
| INTENTIONALLY_NOT_CALLED_DIRECTLY | 2 |
| NOT_APPLICABLE | 0 |
| **RUNTIME_REQUIRED_OMISSIONS** | **0** |
| **NORMAL_RUNTIME_DIRECT_STATE_MUTATIONS** | **0** |

PCA-8 PASS · PCA-15 PASS · PCA-16 PASS · PCA-18 PASS.
