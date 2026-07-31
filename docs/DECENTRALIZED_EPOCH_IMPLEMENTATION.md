# Decentralized Decision-Epoch Implementation

Implementation `rvt_swarm/decentralized/epoch.py` ·
Tests `tests/test_epoch_protocol.py`, `tests/test_mode_confirmation.py`

> **Status: implemented and fully tested (38/38 functions exercised), but NOT
> yet wired into `runtime.py`.** Every closed-loop number in the seed-0 gate
> report came from `runtime.py`'s inline `step % decision_interval` timer, which
> has no trigger, no token, and no confirmation. Wiring this module in is Task 9.
> Until then, treat this document as a specification with test evidence, not as
> a description of what the reported experiments ran.

---

## 1. State machine

```
IDLE ------- local_trigger fires (own sensors only) -------> TRIGGERED
  ^                                                              |
  |                                            max-consensus on trigger flag
  |                                                              v
  |                                                          SCORING
  |                                            k_score rounds of MH consensus
  |                                                              v
  |                                                        CONFIRMING
  |                                       k_confirm rounds of min/max consensus
  |                                                              v
  +------- remaining_commitment reaches 0 <----------------- COMMITTED
```

Per-robot state (`EpochState`): `robot_id`, `epoch_counter`, `epoch_id`,
`trigger_token`, `trigger_timestamp`, `phase`, `consensus_round`,
`committed_mode`, `remaining_commitment`, `trigger_flag`, `mode_lo`, `mode_hi`.

Every field is robot *i*'s own. No robot holds another robot's state, and no
object holds the fleet's state with authority.

## 2. Why it is leaderless

Two independent robots can trigger simultaneously. They are reconciled by a
**deterministic total order on trigger tokens**, not by an election:

```
TriggerToken = (epoch_counter, trigger_timestamp, robot_id)
```

`token_max` is associative and commutative, so max-consensus over tokens
converges to the same winner in every connected component regardless of message
order or arrival sequence. `robot_id` appears only as the final tie-break after
`epoch_counter` and `trigger_timestamp` — it breaks ties, it does not confer
authority. A robot with a low id has no special power: it wins only when two
robots trigger in the same step of the same epoch counter, which is exactly the
case that needs an arbitrary but consistent rule.

`epoch_id_from_token` derives the epoch id from the winning token, so all robots
in a component agree on *which* epoch they are in without anyone announcing it.

## 3. Local trigger

`local_trigger(view, cfg, state)` reads only robot *i*'s `RobotView`. Thresholds
(`TriggerThresholds.from_config`), each derived from an existing env constant
rather than tuned:

| input | threshold | source |
|---|---|---|
| own nearest sensed obstacle clearance | `< 0.90 m` | `nominal_spacing` — below one spacing the formation cannot hold its width |
| own displacement along the mission direction | `< 0.135 m` over 5 steps | `max_speed × dt × 5 × 0.2` — under 20 % of free-running progress |
| own local formation error | `> 0.55 m` | `formation_tolerance` |
| decision interval expiry | `25` steps | fallback only; see Task 9 |

There is no global trigger. Nothing aggregates clearance, progress, or formation
error across robots before the trigger is evaluated.

## 4. Message schemas

| message | bytes | fields |
|---|---|---|
| `TriggerMessage` | **21** | `sender_id` u16 · `epoch_counter` u32 · `trigger_flag` u8 · token `(u32,u32,u16)` · `timestamp_step` u32 |
| `ConfirmMessage` | **16** | `sender_id` u16 · `epoch_id` u32 · `selected_mode` u8 · `margin` f32 · `confirm_round` u8 · `timestamp_step` u32 |

Both verified by `comm_cost.assert_schema_sizes()`. Neither has a list-valued
field, so neither can relay a neighbour list or carry anyone else's state.

`selected_mode` is a mode-**set** code, not a plain mode: confirmation runs min
*and* max consensus simultaneously, so the packet must carry both bounds.
`MODE_SET_MIXED` is the code meaning "min ≠ max", i.e. disagreement detected.

## 5. Mode confirmation

Robot *i* commits only when **all** hold locally:

1. observed `mode_lo == mode_hi` (min-consensus and max-consensus agree);
2. the epoch id matches its own;
3. `margin ≥ confirm_margin`.

On failure it **retains its previous committed mode**, records a
`DisagreementEvent`, and selects no fallback. There is no "default to keep" path:
choosing an arbitrary mode on disagreement would manufacture agreement that the
protocol did not achieve.

After either outcome the robot commits for `h_commit = 10` control steps, during
which the mode cannot change.

## 6. Behaviour under adverse conditions

| condition | behaviour |
|---|---|
| simultaneous triggers | token order picks one epoch deterministically; tested in both arrival orders |
| duplicated triggers | idempotent — a repeated message changes no state |
| lost messages | fewer terms applied; the robot keeps its own value; never replaced with future information |
| delayed messages | accepted while age ≤ `delta_stale_steps = 3`; rejected as stale beyond it |
| stale messages | rejected and counted |
| disconnection | each component runs its own epoch and confirms independently; **component agreement is reported, swarm-wide agreement is not claimed** |
| disagreement timeout | previous mode retained, event recorded |
| overlapping epochs | rejected by epoch-id mismatch |

## 7. Test evidence

`tests/test_epoch_protocol.py` and `tests/test_mode_confirmation.py` exercise
**38/38** functions in `epoch.py` (measured with `trace.Trace`, previously 0/38).
Covered behaviours include: no leader/coordinator object exists; no epoch is
initiated centrally; duplicate and stale messages are ignored; simultaneous
triggers resolve deterministically; passing an obs dict or an `(N,2)` array
raises; commitment lasts exactly `h_commit`; token ordering is antisymmetric and
transitive; `token_max` is associative and commutative; mode-set codes round-trip;
confirmation detects disagreement and retains the previous mode; and disconnected
components yield `agreement_rate == 0` with `component_agreement == 1.0`.

## 8. Known gap

`runtime.py` does not import this module. Consequently:

- Gate D2's "mode-confirmation success ≥ 0.95" has **no closed-loop measurement**.
  `test_mode_confirmation.py` measures it at the protocol level on synthetic
  proposals, which is a different and weaker claim, and is labelled as such.
- Trigger and confirmation communication costs are budgets, not measurements
  (`DECENTRALIZED_COMMUNICATION_ACCOUNTING.md` §4).

Both are resolved by Task 9, which replaces the periodic timer with
event-triggered epochs driven by this module.
