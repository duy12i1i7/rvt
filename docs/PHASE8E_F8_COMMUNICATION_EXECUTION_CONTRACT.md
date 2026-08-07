# Phase 8E F8 Communication Execution Contract

## Base channel

At every `communication_period_seconds`, an undirected physical edge exists iff
current Euclidean robot distance is at most `communication_range_meters`.
Delivery is modeled per direction. Each robot emits the message schemas required
by its current Phase 7 state. Neighbour tables exclude messages older than
`maximum_message_age_seconds`; stale messages never enter controller features or
agreement.

For any connected N-robot component, `D_max=N-1`. Intent, score, readiness and
confirmation rounds remain derived from the declared diameter contract. The
addendum does not alter Phase 7 state transitions.

## Bounded delay and loss

For `bounded_delay_loss`, each directed message draws delay uniformly from
`[0,layout.delay_s]` and is delivered at the first communication tick at or after
`send_time+delay`. Drop is Bernoulli with probability `layout.packet_loss`.
Counter key is
`communication_seed,sender,receiver,sequence,message_type,delay_or_drop`.
This profile is bounded degradation inside method assumptions because stored
delay remains below freshness and no intentional graph cut is imposed.

## Temporary disconnection

`temporary_disconnection_then_restore` applies the same stored delay/loss process
and one deterministic partition cut.

Let `d_entry` be distance from `start_center_meters` to the first compiled passage
entry, `v_max` the platform speed and `T_comm` the communication period.

`start_tick = ceil(d_entry / v_max / T_comm)`

`duration_ticks = 2*(D_max+1)`

At those ticks all messages crossing the role-ordinal partition
`[0,ceil(N/2)) | [ceil(N/2),N)` are dropped. Cross-cut messages already queued
are dropped and never delivered after restoration. At the first tick after the
duration, ordinary distance edges resume with empty cross-cut queues. Same seed,
layout and N always produce the same schedule.

The cut is an explicit assumption-violation stress interval, not bounded nominal
degradation. Protocol abort, timeout or task failure caused by the declared cut
is a legitimate valid task-negative in F8. A malformed or incorrectly executed
schedule is generation-invalid. Runtime does not decide this classification.

Snapshot state comprises communication tick, per-link sequence numbers, queued
serialized messages and delivery ticks, PRF identity, neighbour-table timestamps
and cut-active state. Paired candidates use the same counter-keyed delay/drop/cut
schedule. Candidate motion may legitimately change range-gated physical edges;
that is treatment response, not unmatched randomness.

Rejected alternatives were the Phase 7 fixture's middle causal-round cut,
wall-clock random loss, delay rounded down to zero, queued delivery after
restoration, and treating the declared stress episode as evaluator-invalid.
Those choices either depend on protocol progress, worker timing, or erase the F8
research condition.
