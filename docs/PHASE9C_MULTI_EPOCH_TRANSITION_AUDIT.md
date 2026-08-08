# Phase 9C — Multi-Epoch Transition Audit (Defect 12)

## Root cause — classification A

The adapter failed to invoke retirement logic the frozen protocol already
specifies. Read directly from `transition_protocol.TransitionProtocolNode`:

```python
def mark_complete(self, now_seconds):
    if self.state != "TARGET_DWELL" or not self.local_dwell_complete:
        raise TransitionProtocolError("completion requires local target dwell")
    self.rearm_started_seconds = float(now_seconds)
    self._advance("COMPLETE", now_seconds)      # active_intent NOT cleared

def try_rearm(self, now_seconds):
    if self.state not in ("ABORTED", "COMPLETE"):
        return False
    if now_seconds - self.rearm_started_seconds + 1e-12 < rearm_inactive_seconds:
        return False
    self.active_intent = None
    self._score_agreed = False
    self._all_ready = False
    self._confirmed = False
    self.dwell_started_seconds = None
    self.local_dwell_complete = False
    self._advance("REARMED", now_seconds)
    return True
```

`mark_complete` deliberately leaves `active_intent`, `_score_agreed`,
`_all_ready`, `_confirmed` and the dwell clock **latched**. `try_rearm` is the
frozen retirement step, gated by `rearm_inactive_seconds = 3.75 s`.

**The adapter never called `try_rearm`.**

## First divergent invariant

Immediately after epoch 1 reached COMPLETE, every node still held its finished
C->L intent. `_active_intent(session)` returned that stale intent, so
`advance_transition_lifecycle` kept driving the completed epoch and no second
lifecycle could ever begin. That is the first state that differs from a valid
first epoch, and everything else observed downstream was a symptom of it.

## Repair — frozen calls only

1. `_retire_finished_lifecycles` calls the frozen `try_rearm` per robot on nodes
   in COMPLETE or ABORTED, and clears the retired transition executor. An AST
   test asserts `try_rearm` is the *only* method it calls, so no reset rule is
   invented and no central shortcut exists.
2. `_active_intent` skips nodes in terminal states, so a COMPLETE node inside
   its rearm window cannot re-drive its finished epoch.
3. Adoption now matches the frozen `adopt_intent` precondition set
   (`STABLE_TOPOLOGY`, `REARMED`, `COMPLETE`). Restricting it to
   `STABLE_TOPOLOGY` left rearmed nodes without an active lifecycle, and the
   next phase raised "score requires active lifecycle".
4. Agreement messages are emitted only by nodes that actually hold an active
   intent.

No scientific semantics, threshold or lifecycle state was added.

## Verified result

`train-f1-00`, N=6, from the common COMPACT start via S2's forced
initialization, then two further forced diagnostic epochs:

| epoch | transition | committed after | `mode_epoch_count` |
|---:|---|---|---:|
| 1 | COMPACT -> LINE | LINE | 1 |
| 2 | LINE -> COMPACT | COMPACT | 2 |
| 3 | COMPACT -> LINE | LINE | 3 |

Epoch identifiers monotonic, fresh profile per epoch, no stale agreement or
dwell state, no collision, `topology_selection_epoch_count` remains 0 for forced
diagnostic requests.

## Remaining work

`headroom_requalification_v5` is marked `PROVISIONAL_PRE_D12`: its switching
outcomes predate this repair, so any cell whose diagnostic needed a second epoch
may be misclassified. The v6 sweep and the clean-checkout reproduction were not
run.

Five older case-4 fixtures in `test_phase9c_phase7_live_lifecycle.py` remain
`xfail(strict=True)`: chaining a further epoch from that particular fixture is
unresolved. The D12-required functionality itself is covered and passing in
`test_phase9c_two_epoch_transition.py` and
`test_phase9c_three_epoch_transition.py`.
