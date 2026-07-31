# Decentralized Reconfiguration State Machine

Two modes, `KEEP` and `LINE`. Two transitions, `KEEP -> LINE` and `LINE -> KEEP`.
`epoch.py` is the sole authoritative implementation; `runtime.py` calls it and
holds no protocol logic of its own.

Tests: `tests/test_reconfiguration_state_machine.py` (13),
`tests/test_decentralized_runtime_integration.py` (16).

---

## 1. Per-robot state

Every robot stores locally, in its own `EpochState`: `robot_id`,
`epoch_counter`, `epoch_id`, `trigger_token`, `trigger_timestamp`, `phase`,
`consensus_round`, `committed_mode`, `remaining_commitment`, `trigger_flag`,
`mode_lo`, `mode_hi`, `margin_min`, `own_proposal`, `own_margin`,
`confirm_round`, plus counters (`disagreements`, `commits`, `retentions`,
`rejected_stale`, `rejected_future`, `rejected_self`).

No robot holds another robot's state. There is no epoch clock and no event
initiator outside the robots themselves.

## 2. Phases

```
IDLE --local trigger (own sensors)--> TRIGGERED --max-consensus--> SCORING
                                                                      |
                                                        k_score MH rounds
                                                                      v
   IDLE <--remaining_commitment == 0-- COMMITTED <--commit_or_retain-- CONFIRMING
```

## 3. Transition preconditions

`KEEP -> LINE` requires, in order:

1. a robot-local constrained-passage trigger (`local_trigger`);
2. neighbour-to-neighbour trigger propagation (`simulate_trigger_consensus`);
3. leaderless score consensus (`simulate_consensus`);
4. peer mode confirmation (`simulate_confirm_consensus`);
5. agreement within the connected component (`commit_or_retain`).

`LINE -> KEEP` requires the same five steps, with step 1 replaced by
`local_recovery_trigger`.

## 4. The two triggers are asymmetric by construction

| trigger | condition | threshold | source |
|---|---|---|---|
| entry (`KEEP -> LINE`) | own sensed clearance **below** | `0.90 m` | `max(nominal_spacing, min_ro_distance)` |
| recovery (`LINE -> KEEP`) | own sensed clearance **at or above** | `1.80 m` | `2 x nominal_spacing` |

`recovery_clearance_m > clearance_m` strictly, so no geometry can fire both --
asserted over a sweep of clearances in `test_02b`. The recovery trigger
additionally requires `committed_mode == LINE`, so it cannot fire in KEEP.

Both read only robot *i*'s own `RobotView`. The exit plane of
`DECENTRALIZED_RECONFIGURATION_TASK_V2.md` is an **offline scoring construct**
and is never a runtime input; a robot infers passage from its own clearance
reopening, not from knowing where the structure ends.

## 5. Failure handling

Confirmation commits only when, judged from robot *i*'s own observations,
`mode_lo == mode_hi`, `epoch_mismatch == 0`, and `margin_min >= confirm_margin`.
Otherwise the robot **retains its previous committed mode**, records a
`DisagreementEvent`, and invents no fallback. There is no "default to keep"
path: two robots defaulting from different previous modes would split the team
while appearing to agree.

Oscillation is bounded by `h_commit = 10` control steps. A locked robot refuses
to re-trigger in either direction (`test_06`), so the minimum time between
transitions is the dwell interval.

## 6. Adverse conditions

| condition | behaviour | test |
|---|---|---|
| simultaneous triggers | token order picks one epoch; arrival order is irrelevant | `test_08` |
| stale trigger token | rejected, cannot reopen a closed epoch | `test_07` |
| delayed confirmation beyond `Delta_stale` | traffic dropped, **every** robot retains, no partial commitment | `test_09` |
| disconnected components | distinct epoch ids per component; no swarm-wide claim | `test_10` |
| trigger noise inside the dwell | refused | `test_06` |

## 7. What a real episode does

On `line_corridor`, N=6, seed 20000001, scripted geometric proposals:

```
step  0  KKKKKK
step 30  KKKKKK
step 40  LLLLLL      <- KEEP -> LINE, all six robots, one epoch
step 84  LLLLLL
```

11 event-triggered epochs, `n_keep_to_line = 6`, full agreement 0.909,
6 disagreement events (retentions, not splits), and all four message categories
non-zero.

**`n_line_to_keep = 0`.** The team enters line and does not recover to keep in
this layout. Whether that is a missing recovery region, a controller limitation,
or a timing problem is exactly what Task 4 measures; it is recorded here rather
than presented as a working round trip.
