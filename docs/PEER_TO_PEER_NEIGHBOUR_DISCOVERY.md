# Peer-to-Peer Neighbour Discovery

Implementation: `rvt_swarm/decentralized/comms.py`
Contract: `rvt_swarm/decentralized/system_model.py` (parameters, `RobotView`, `NeighbourRecord`)
Tests: `tests/test_neighbour_discovery.py` (29 tests)

Robot *i* discovers its neighbours by listening, not by being told. There is no
registry, no lookup service, and no entity that knows the swarm. Every entry in
robot *i*'s neighbour table exists because a packet from that sender physically
arrived at robot *i*, and every entry is stored ego-relative so that a
neighbour's absolute pose does not survive ingestion.

```
own state ──► build_beacon ──► RadioChannel ──► peer inboxes
                                (range, loss, delay)
peer beacons ──► NeighbourTable.ingest ──► prune ──► neighbours() ──► RobotView
                 (absolute → ego-relative)   (staleness)
```

---

## 0. Parameters

All taken from `system_model.CommParams`; nothing is re-derived here.

| Symbol | Field | Value | Role |
|---|---|---|---|
| `R_comm` | `r_comm` | 3.0 m | link exists iff separation ≤ this |
| `R_obs` | `r_obs` | 3.0 m | own-sensor obstacle horizon |
| `Δ_stale` | `delta_stale_steps` | 3 steps | maximum accepted message age |
| `t_comm`, `t_ctrl` | | 0.15 s | one beacon per control step |
| `p_loss` | `packet_loss` | 0.0 nominal | per-message Bernoulli loss |
| `d_delay` | `delay_steps` | 0 nominal | delivery latency, control steps |
| — | `PROGRESS_WINDOW_STEPS` | 5 steps | own-history window for `local_progress` |
| — | `SEEN_SEQ_HORIZON` | 64 | per-sender duplicate memory |

---

## 1. Beacon schema

A `Beacon` is the complete over-the-air packet — a frozen dataclass with exactly
eleven fields and no others. Absolute pose is permitted *inside* a beacon
because that is literally what a radio transmits; it is differenced away at the
instant of ingestion (§3) and never stored.

| # | Field | Python type | Wire type | Bytes | Notes |
|---|---|---|---|---|---|
| 1 | `sender_id` | `int` | `uint16` | 2 | persistent robot ID |
| 2 | `timestamp_step` | `int` | `uint32` | 4 | control step at which the state was sampled |
| 3 | `seq` | `int` | `uint32` | 4 | per-sender monotone counter, starts at 1 |
| 4 | `position` | `(float, float)` | `2 × float32` | 8 | absolute, sender frame-shared |
| 5 | `velocity` | `(float, float)` | `2 × float32` | 8 | absolute |
| 6 | `role_keep` | `(float, float)` | `2 × float32` | 8 | template-frame role coordinate, KEEP |
| 7 | `role_line` | `(float, float)` | `2 × float32` | 8 | template-frame role coordinate, LINE |
| 8 | `committed_mode` | `int` | `uint8` | 1 | `KEEP=0` or `LINE=2` |
| 9 | `epoch_id` | `int` | `uint32` | 4 | sender's decision epoch |
| 10 | `degree` | `int` | `uint8` | 1 | sender's own one-hop degree (a scalar count) |
| 11 | `valid` | `bool` | `uint8` | 1 | sender asserts its own state is usable |

**Total payload: 49 bytes**, verified by
`Beacon.payload_bytes()` and asserted in `test_beacon_schema_is_exactly_the_declared_field_list`.
Encoding is little-endian, unpadded: `struct` format `"<HII8f BIBB"`.

The field list is deliberately closed and contains **no list-valued field**. A
beacon therefore cannot carry a neighbour list, a routing table, or a relay
payload. This is the structural half of the one-hop rule (§9).

`degree` is the only aggregate a sender transmits. It is a count over the
sender's own table, not a set of identities, and it carries no peer state.

---

## 2. Neighbour table fields

`NeighbourTable` is per-robot and deployable: it holds the robot's own position
plus one record per sender it has heard. The stored record (`_Entry`) has these
fields; the public read model is `NeighbourRecord` from the contract.

| Stored field | Type | Source | Notes |
|---|---|---|---|
| `robot_id` | `int` | `beacon.sender_id` | |
| `seq` | `int` | `beacon.seq` | highest accepted sequence number |
| `first_seq` | `int` | first accepted `seq` | denominator for the loss estimate |
| `accepted` | `int` | counter | numerator for the loss estimate |
| `timestamp_step` | `int` | `beacon.timestamp_step` | basis of the staleness rule |
| `rel_position` | `(float, float)` | `p_j − p_i` | **ego-relative, never absolute** |
| `rel_velocity` | `(float, float)` | `v_j − v_i` | **ego-relative, never absolute** |
| `role_keep`, `role_line` | `(float, float)` | beacon | template-frame constants |
| `committed_mode` | `int` | beacon | |
| `epoch_id` | `int` | beacon | |
| `degree` | `int` | beacon | neighbour's own degree |
| `valid` | `bool` | beacon | sender's self-assessment |
| `stale_marked` | `bool` | `prune()` | bookkeeping, see §5 |

Derived on read into a `NeighbourRecord`:

* `message_age_steps = now_step − timestamp_step`
* `link_valid = entry.valid`
* `packet_loss_estimate = clamp(1 − accepted / (seq − first_seq + 1), 0, 1)` —
  computed from robot *i*'s own reception record alone.

`neighbours(now_step)` is **pure** (it does not mutate) and returns records
**sorted by `robot_id`**, so the tuple is a function of what arrived and not of
the order in which it arrived. That is what makes downstream consensus rounds
reproducible. Asserted by `test_neighbour_order_is_id_sorted_not_arrival_sorted`.

### Counters (public API)

`duplicates_rejected`, `out_of_order_rejected`, `stale_rejected`,
`unknown_id_accepted`, `reappeared`, plus the supplementary
`accepted`, `self_rejected`, `future_rejected`, `stale_pruned`.
Every rejected beacon increments **exactly one** counter and leaves stored state
untouched.

---

## 3. Ingestion: absolute → ego-relative

Before each round the robot writes its own current pose into its table
(`set_own_position`). On acceptance:

```
rel_position = beacon.position − own_position
rel_velocity = beacon.velocity − own_velocity
```

The absolute values are consumed by that subtraction and are never assigned to
any field. Consequences, both asserted:

* Translating the entire swarm by a constant leaves every table **byte-identical**
  (`test_neighbour_state_is_invariant_to_a_rigid_shift_of_the_whole_swarm`). The
  test coordinates are dyadic so the shift is exact in float64 and the assertion
  tests the invariant rather than floating-point associativity.
* No absolute coordinate of any other robot is reachable by a recursive walk of a
  `RobotView` or a table
  (`test_no_absolute_neighbour_position_is_reachable_from_a_view`).
* `NeighbourRecord` has no `position` or `velocity` field at all — only
  `rel_position` / `rel_velocity`.

---

## 4. Rejection order

Fixed and total. The first matching rule wins:

```
1. sender_id == own id                              → self_rejected
2. timestamp_step > now_step                        → future_rejected
3. now_step − timestamp_step > Δ_stale              → stale_rejected
4. (sender_id, seq) already seen                    → duplicates_rejected
5. sender known and seq ≤ stored seq                → out_of_order_rejected
6. otherwise                                        → accept
```

Rule 2 exists because a packet stamped in the future would be exactly the
"delivery replaced by future information" failure mode. Rule 4 is evaluated
before rule 5 so that an exact retransmission is labelled *duplicate* rather
than *out-of-order*.

---

## 5. Staleness rule

```
age = now_step − timestamp_step
fresh  ⟺  0 ≤ age ≤ Δ_stale        (Δ_stale = 3 control steps = 0.45 s)
```

* A beacon that **arrives** with `age > Δ_stale` is rejected outright
  (`stale_rejected`) and does not create or update an entry.
* A record whose age **grows** past `Δ_stale` is excluded from `neighbours()` and
  from `degree()` immediately, whether or not `prune()` has run — freshness is
  evaluated at query time, so a missed `prune()` call cannot serve stale data.
* `prune(now_step)` marks such records (`stale_marked`, `stale_pruned`) and
  returns their IDs. It **marks rather than deletes**, for two reasons:
  1. the sequence bookkeeping survives, so a replayed pre-silence packet from a
     neighbour that went quiet is still rejected (§8);
  2. reappearance is detectable and countable (§8).

Boundary: `age == Δ_stale` is fresh, `age == Δ_stale + 1` is stale. Asserted
explicitly across the whole range in `test_stale_neighbour_is_removed`.

Justification of the value is in `system_model.CommParams`: at `max_speed`
0.9 m/s a neighbour moves at most 0.405 m in 3 steps, well inside
`nominal_spacing` 0.9 m.

---

## 6. Duplicate handling

A beacon whose `(sender_id, seq)` has already been observed is rejected and
`duplicates_rejected` is incremented. It cannot create a second entry, and it
cannot perturb the stored state — the table is keyed by `sender_id`, so
duplicate suppression is structural as well as explicit.

Duplicate memory is bounded: each sender's most recent `SEEN_SEQ_HORIZON = 64`
sequence numbers are retained. Nothing is lost by the horizon, because any `seq`
older than the stored one is rejected by the out-of-order rule anyway; the
horizon only affects which *label* a very old retransmission receives.

*Test:* `test_duplicate_messages_do_not_create_duplicate_neighbours` — five
retransmissions produce one neighbour, `duplicates_rejected == 5`, `accepted == 1`,
and the stored relative position is unchanged.

---

## 7. Out-of-order handling

A beacon with `seq ≤ stored seq` is rejected and **must not overwrite newer
state**. This is a separate rule from staleness: an out-of-order beacon can be
perfectly fresh by timestamp and is still rejected, because sequence order —
not arrival order — defines which state is newer.

*Tests:*
* `test_out_of_order_message_cannot_overwrite_newer_state` — after ingesting
  `seq=5` then `seq=3`, the stored position, velocity, epoch and mode are all
  still the `seq=5` values, and the `seq=3` payload leaves no trace anywhere in
  the table.
* `test_out_of_order_rejection_is_not_a_staleness_rejection` — both beacons are
  inside the staleness window, `stale_rejected == 0`, so the rejection is
  demonstrably attributable to sequence order.

---

## 8. Unknown-ID and reappearing-neighbour handling

**Unknown ID.** A beacon from a sender with no entry is accepted by creating
one, and `unknown_id_accepted` is incremented once. Discovery needs no prior
knowledge of the roster: robot *i* does not know how many robots exist, and
never learns. Subsequent beacons from the same sender do not increment the
counter again.

**Reappearing neighbour.** A sender that went silent long enough to go stale and
then transmits again is re-admitted: the record is refreshed, `stale_marked` is
cleared, and `reappeared` is incremented once per readmission. Because the
record was marked and not deleted, its `seq` survived the silence, so a replayed
pre-silence packet is *still* rejected after readmission — silence is not an
opening for a replay attack or for a stale packet flushed out of a queue.

*Tests:* `test_unknown_id_is_accepted_by_creating_an_entry`,
`test_reappearing_neighbour_is_readmitted_and_counted` (which also asserts the
post-readmission replay rejection), `test_a_robot_rejects_its_own_beacon`.

---

## 9. Simultaneous-message handling

Several beacons may be ingested at the same `now_step`.

* **Different senders, same step.** Order-independent by construction: the table
  is keyed by `sender_id`, and `neighbours()` sorts by `robot_id`. Ingesting a
  batch forwards and backwards yields byte-identical `canonical_bytes` and
  identical counters.
* **Same sender, two sequence numbers, same step.** The final stored state is
  always the higher `seq`, in either arrival order — ascending accepts both,
  descending accepts the first and rejects the second as out-of-order. The
  *counters* differ (that is the point of having them), the *state* does not.
* **Delivery order within one round** is fixed by the channel: `deliver()` sorts
  by `(dst_id, sender_id, seq)`, so it is a function of the trace and never of
  dict iteration order.

*Test:* `test_simultaneous_messages_give_an_order_independent_result`.

---

## 10. The one-hop-only rule

> **Robot *i*'s table may contain state that originated at robot *j* only if a
> packet travelled directly from *j* to *i*. There is no relaying, no
> forwarding, and no gossip of third-party state.**

Enforced three ways:

1. **Structurally.** The `Beacon` schema (§1) has eleven scalar/pair fields and
   no container. There is no field in which a neighbour list could travel, so
   forwarding is not merely disabled — it is unrepresentable.
2. **By construction.** `build_beacon` reads only the emitting robot's own state
   and its own `degree`. `ingest` writes only fields derived from the single
   beacon in hand.
3. **Executably.** In the chain A(0) — B(1) — C(2) with A–C separation 5.0 m
   > `R_comm` = 3.0 m:
   * `test_no_two_hop_forwarding` asserts B sees `(0, 2)` while A sees only
     `(1,)`, that A's table has `known_ids() == (1,)`, and that none of C's
     distinctive scalars is reachable by a recursive walk of A's view and table.
     The same scan is shown to be non-vacuous by confirming that B's relative
     state *is* present.
   * `test_two_hop_state_change_leaves_table_byte_identical` changes C's
     position, velocity and epoch while keeping C inside B's range and outside
     A's, then asserts A's `canonical_bytes`, digest, view bytes and counters are
     **byte-identical** across the two runs — while separately asserting that B
     did notice the change, so the invariance is not vacuous.

**What legitimately does propagate.** B's transmitted `degree` changes if C
enters or leaves B's range, and A can observe that scalar. That is a one-hop
observation of B's own state, it is in the declared schema, and it conveys no
identity and no state of C. The test above holds C inside B's range precisely so
that this permitted channel is held constant and the prohibited one is isolated.

---

## 11. The simulation boundary

`simulate_broadcast_round` is the **only** function in
`rvt_swarm.decentralized` permitted to read the global simulator state — the
(N,2) position and velocity arrays, the full obstacle array, and the per-robot
mode/epoch arrays. It stands in for the radio and the sensors and returns
`Dict[int, RobotView]`. It is **not deployable**; on hardware it does not exist,
because the radio driver fills the table and the lidar driver fills `obstacles`
directly.

Round order — emit → transmit → deliver + ingest → prune → own-history update →
view construction. Emission uses the degree the robot knew at the *start* of the
round, so no robot's beacon can depend on a packet it has not yet received.

Two helpers are also simulation-only and carry the `simulate_` prefix:

* `simulate_local_obstacles(own_position, obstacles, obstacle_radius, r_obs)` —
  the lidar gate. Robot *i* receives only obstacles with `‖q − p_i‖ ≤ R_obs`, as
  `(rel_x, rel_y, radius)` relative to `p_i`, ordered by distance then index.
  The full obstacle array is a prohibited obs key; this gate is why it never
  reaches a feature builder.
* `RadioChannel` — the link model. It never takes a positions array: the
  boundary hands it one source pose and one destination pose at a time, so the
  "one function sees the joint state" property holds literally.

`test_only_simulate_prefixed_functions_take_global_state` walks every
module-level function in `comms.py` and asserts that no function without the
`simulate_` prefix has a parameter named `positions`, `velocities`, `obstacles`,
`obs`, `obs_dict`, `all_positions` or `states`.

### Channel determinism and causality

The drop decision and the delivery step are both fixed at transmission time from
`(seed, step, src, dst)` and the two poses at that step. The Bernoulli draw is a
pure hash (`blake2b` over the packed key), not a stateful RNG:

```
u = blake2b(pack("<qqqq", seed, step, src, dst)) / 2^64 ;  drop iff u < p_loss
```

so the decision for one link is independent of how many other draws were taken,
of iteration order, and of whether the episode was resumed. Delivery is
scheduled at `step + d_delay` and served only at exactly that step; anything
found scheduled in the past is counted `dropped_expired` rather than delivered
late. Nothing later can revise either decision, so no future information can
leak backwards.

*Tests:* `test_delivery_decision_is_independent_of_unrelated_transmissions`
(the same 36 link decisions after 0 and after 17 unrelated transmissions, with
an assertion that the outcomes are mixed so the test is not vacuous),
`test_delayed_packet_arrives_exactly_at_send_step_plus_delay`,
`test_delivery_draw_depends_only_on_seed_step_src_dst`.

---

## 12. `local_progress`

`RobotView.local_progress` is robot *i*'s **own** displacement along the shared
mission direction over its own last `PROGRESS_WINDOW_STEPS = 5` control steps:

```
local_progress = (p_i(t) − p_i(t − 5)) · û_mission
```

computed by `OwnHistory`, which stores nothing but robot *i*'s own poses. It is
not the swarm's progress, not a centroid displacement, and not comparable across
robots. The prohibited obs key `progress` (centroid-derived) never appears.

*Test:* `test_local_progress_uses_only_the_robots_own_history` — robot 0's
`local_progress` trace is identical across two runs in which robot 1 follows
different trajectories, while asserting that robot 1 genuinely moved differently.

---

## 13. Verification status

Command:

```
cd /Users/udy/rvt && PYTHONPATH=. .venv/bin/python -m pytest tests/test_neighbour_discovery.py -q
```

Result: **29 passed, 0 failed**. Full suite at time of writing: **286 passed**,
no regressions. (The full-suite total moves as sibling decentralization modules
land on this branch; the 29 above is the number for this component.)

A mutation check (11 deliberate defects injected into `comms.py`, one at a time)
was used to confirm the tests fail for the right reason. **11 / 11 were caught**:
dropping duplicate rejection, dropping out-of-order rejection, dropping ingest
staleness rejection, serving stale records from `neighbours()`, storing absolute
instead of relative position, removing the radio range gate, removing the
obstacle range gate, sorting neighbours by arrival instead of ID, keying the loss
draw on a stateful counter instead of `(seed, step, src, dst)`, delivering queued
packets early, and forwarding a sender's neighbour list into its beacon.

The ninth of those initially **survived**, because replaying an identical trace
cannot distinguish a pure hash from a stateful RNG. That gap was closed by adding
`test_delivery_decision_is_independent_of_unrelated_transmissions`, which is the
test that now catches it.

## 14. Limitations

* Neighbours come from **communication only**. `r_sense = 4.0 m` is declared in
  the contract but is not used to populate `N_i`; a robot that is visible but
  silent is not a neighbour. This is the stricter and more testable choice.
* No connectivity assumption. Discovery is purely local; whether `G_c` is
  connected is a measured property of an episode, never an input.
* Sequence numbers are `uint32` and monotone per sender. Wraparound is not
  handled; at one beacon per 0.15 s that is ~20 years of continuous operation.
* `packet_loss_estimate` is a naive gap-counting estimator over the observed
  sequence range. It is a diagnostic, and no result depends on its accuracy.
* A shared coordinate frame and a shared mission direction are assumed, as
  declared in `roles.ROLE_LIMITATIONS`. Ego-relative storage removes the need for
  a shared *origin*, but not for a shared *orientation*.
