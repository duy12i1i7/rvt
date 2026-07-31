# Decentralized Trigger Latching (Task 5-7)

`epoch.py`: `update_passage_latch`, `entry_trigger_allowed`,
`recovery_trigger_allowed`, `latched_local_trigger`, `note_transition`.
Tests: `tests/test_decentralized_trigger_latching.py`.

## Lifecycle

```
BEFORE_ENTRY --(confirmed K->L)--> INSIDE_PASSAGE --(confirmed L->K)--> COMPLETE
     ^                                                                     |
     +------------- REARM_OPEN_STEPS (25) of open clearance ---------------+
```

Per robot, driven only by its own sensed clearance and its own committed mode.
No peer state, no bottleneck identity, **no central tracker**.

| requirement | mechanism |
|---|---|
| 1. entry disabled while committed to LINE | `entry_trigger_allowed` requires `committed_mode == KEEP` |
| 2. no second entry epoch for the same bottleneck | latch moves to `INSIDE_PASSAGE` on a confirmed K→L |
| 3. recovery disabled until the exit condition | `recovery_trigger_allowed` requires `INSIDE_PASSAGE` |
| 4. no repeated recovery epochs | latch moves to `COMPLETE` on a confirmed L→K |
| 5. no-op proposals cannot create a confirmation phase | pre-arm check plus the post-score no-op guard |
| 6. no new epoch during the commitment interval | `local_trigger`/`local_recovery_trigger` refuse while `locked` |
| 7. hysteresis uses local state only | own clearance streak; nothing shared |
| 8. no central bottleneck tracker | none exists |
| 9. legitimate retries survive | a proposal differing from the committed mode always runs confirmation |
| 10. a later distinct bottleneck re-arms | 25 consecutive open-clearance steps reset the latch |

## Two further changes this required

**Entry trigger reasons narrowed** to `low_clearance` and `low_progress`.
Removed: `local_formation_error` (a *consequence* of a tight passage, not
independent evidence — it fired 87 times in one always-KEEP episode and
re-opened epochs in open space) and `interval_expiry` (a fixed periodic timer,
which Task 3B removed from the deployable path; leaving it in the trigger would
reintroduce periodic decisions through the back door).

**Local no-op pre-arm check.** A robot evaluates its own proposal from its own
view and declines to open an epoch to propose the mode it already holds.
Entirely local — the same computation the epoch would perform anyway.
