# Distributed Event Origination and Adoption (Task 6RR-5)

Tests: `tests/test_event_origination_and_adoption.py` (21)

---

## 1. The distinction

| | ORIGINATION | ADOPTION |
|---|---|---|
| requires local forward-opening evidence | **yes** | **no** |
| requires the frozen persistence rule (`L_TRIGGER = 3`) | **yes** | **no** |
| requires a valid, fresh, compatible peer token | n/a | **yes** |
| requires compatible local mission state | yes | **yes** |
| forces immediate commitment | no | **no** |
| participates in consensus and confirmation | yes | **yes** |

Compatible local state for adopting a RECOVERY event: currently committed to
LINE, inside the same active passage lifecycle (`latch = INSIDE_PASSAGE`), no
conflicting newer epoch, token valid and fresh.

**Not required of an adopting robot:** local forward-opening evidence, local
physical exit, or any access to a global exit plane.

## 2. Why this is the correct semantics

Requiring every robot to rediscover the opening made commitment track the
**last** robot's sensing. Measured pre-repair, per-robot first evidence:

```
robot 4: step 44      robot 2: step 84
robot 5: step 59      robot 1: step 93
robot 3: step 72      robot 0: step 103      ->  commit at 111
```

Post-repair, commitment occurs at **45–46**, before any non-originator has
accumulated evidence at all. The event is a *proposal* that propagates, not a
conclusion each robot must independently reach.

## 3. Why it remains decentralized

- The originating evidence is **local** — a robot's own forward obstacle returns.
- The event propagates **peer-to-peer** by max-consensus on trigger tokens.
- The originator gains **no authority**: `EpochState` has no leader/rank/authority
  field, every robot runs identical acceptance, consensus and confirmation logic,
  and a single robot proposing against a split team **cannot** commit
  (`commit_or_retain` returns False and records a `DisagreementEvent`).
- The requested mode is derived from **lifecycle state**, deterministically and
  identically on every robot: committed KEEP + latch before passage ⇒ LINE;
  committed LINE + latch inside ⇒ KEEP. It is invariant to each robot's own
  clearance — tested at 0.2, 0.5, **0.872**, 1.5, 3.0 and 10.0 m, where 0.872 is
  the exact value that previously cancelled a valid event.
- A `TriggerMessage` carries `{sender_id, epoch_counter, trigger_flag,
  trigger_token, timestamp_step}` — an event proposal. It has **no field
  carrying a mode to execute**, so communication cannot express a command.

## 4. A propagation bound, recorded not tuned around

`k_trigger = 4` propagates at most 4 hops. On a 6-robot **chain** (diameter 5)
an originator at one end reaches five of six robots. The general condition is

```
k_trigger >= diameter(G_c)
```

This does **not** bind in the current runtime: the measured degree across the
post-repair traces is **5 of 5**, i.e. the communication graph at
`r_comm = 3.0` is complete for N = 6 throughout. `k_trigger` is not increased;
the frozen configuration stands and the limitation is stated for any sparser
deployment.
