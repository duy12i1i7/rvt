# Phase 9B Episode and Event Mapping

## Source Classes

The six source classes are fixed independently of candidate outcomes:

| ID | trajectory |
|---|---|
| S0 | scripted diagnostic |
| S1 | always COMPACT |
| S2 | always LINE |
| S3 | frozen local geometric selector |
| S4 | frozen transition-protocol trajectory |
| S5 | bounded perturbation trajectory |

Study A train uses two episodes from each class per cell. Study A validation,
Study A N=24 evaluation and Study B validation use one each.

Study B train uses class-count multiset `(2,2,2,2,1,1)`. Its 120 cells are
sorted by canonical cell hash. A fixed addendum-derived phase and cell hash rank
select a cyclic four-source doubled window. Because 120 is divisible by six,
each source receives exactly 80 doubled assignments plus 120 base assignments,
or 200 episodes globally.

## Event Slots

Five-slot episodes use normalized horizon positions
`[0.10,0.30,0.50,0.70,0.90]`. Four-slot episodes use
`[0.15,0.40,0.65,0.90]`. Each position maps to:

`ceil(normalized_position * horizon_seconds / control_period_seconds)`.

Study B validation has six source episodes per cell. The source selected by the
canonical cell hash receives five slots; the other five receive four, yielding
exactly 25 events per cell.

If an episode terminates before a slot, the slot remains in the denominator as
unavailable with its termination cause. It is not moved or replaced.

## Identity and Seeds

Canonical IDs are hierarchical for source episode, decision event, candidate
replica, residual cell and shard. Duplicate semantic IDs are rejected. Final-test
cells, jobs and seeds cannot be constructed.

Generation seeds use `rvt-generation-seed-sha256-uint32/v1`: sorted ASCII JSON,
SHA-256 and the first four digest bytes interpreted as an unsigned big-endian
integer. The payload contains namespace/root, budget schema, study, split,
family, layout hash, N, source class, episode, optional event slot, candidate and
replica. Worker order is absent, so reordering cannot alter seeds. Model seeds
remain in their separate namespace.
