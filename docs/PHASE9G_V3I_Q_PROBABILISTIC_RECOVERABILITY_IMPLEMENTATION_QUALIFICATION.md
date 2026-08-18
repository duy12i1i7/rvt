# Phase 9G-V3I-Q — Probabilistic Recoverability V3 Additive Implementation and End-to-End Qualification

**Handoff commit:** `6bc983431a885993302f8dd18a1b8eea33d4a7a5`
**Branch:** `research/rvt-phase9g-v3i-q-probabilistic-implementation-qualification-v1`

## Outcome

**STOP: `V3_REPLICA_INVALIDITY_SEMANTICS_OWNER_DECISION_REQUIRED`**

**Verdict D — implementation and qualification incomplete.**
**Recommendation: `DO_NOT_GENERATE_OFFICIAL_V3_DATA`.**

Gate I10 could not be closed from repository authority. I10 states plainly: *"If
this behavior is NOT frozen clearly enough: STOP with
`V3_REPLICA_INVALIDITY_SEMANTICS_OWNER_DECISION_REQUIRED`. Do not guess."* It is
not frozen clearly enough. No V3 code was written, no image was built, and no
canary was run, because every one of those steps encodes the answer.

## I10 — the unfrozen question

> When a **required** candidate replica carries a genuine scientific
> `GENERATION_INVALID` disposition, how is the supervision observation `(k, R)`
> constructed?

### What V3 authority does freeze

| Item | Source | Content |
|---|---|---|
| Mixed replica outcomes are valid supervision | probabilistic target contract | `mixed_outcomes.is_generation_invalid = false`, covering patterns `001`…`110` — disagreement among **valid** replicas |
| Fake `GENERATION_INVALID` from nonexistent source states | gate registry, D3 | threshold 0 |
| Partial candidate-pair publication | gate registry, D4 | threshold 0 |
| Invalid rollout rate | gate registry, S8 | below 0.02 overall, below 0.05 per family |
| Per-replica dispositions are stored | row binding, F6 supervision record | `replica_dispositions` is representable |

Gate S8 is decisive for the framing: it **bounds** the invalid-rollout rate
rather than forbidding it. Invalid rollouts are expected to occur. This is not a
hypothetical edge case.

### What V3 authority does not freeze

The construction of `(k, R)` when fewer than `R` required replicas are
scientifically valid. The frozen replica protocol contains **no statement about
invalid replicas at all** — a full scan of every `phase9d_v3d_*` and
`phase9d_v3f_*` artifact returned nothing on this point.

### The three readings

**A — `CANDIDATE_NOT_LABELABLE`.** Any invalid required replica means the
candidate has no supervision, so the pair publishes 0 robot rows.
Supported by historical Target V4 aggregation (`invalid = not all(valid)`;
`label = int(not invalid and all(outcomes))`), by the frozen rollout protocol
("numerical invalidity sets `invalid` and blocks the row"), and by gate D4 pair
atomicity. Against it: V3 deliberately replaced the all-success aggregation, so
the transfer of this rule is asserted nowhere. Cost: the whole decision event is
dropped, losing both candidates' evidence.

**B — `SHRINK_R_TO_VALID_REPLICAS`. Structurally blocked.** The frozen row
binding states: *"R is bound through `recoverability_replica_protocol_v3_sha256`,
not through an outcome payload field. The protocol fixes R per family, so
identity determines R without recording it."* A data-dependent `R` makes identity
no longer determine `R`, contradicting a frozen contract. The replica protocol
independently sets `adaptive_replication = DISABLED` and
`R_expansion_permitted = false`.

**C — `KEEP_R_COUNT_K_OVER_VALID_ONLY`.** `R` stays at the protocol value; `k`
counts successes among the valid replicas only. The frozen loss is
`-[k·log p + (R−k)·log(1−p)] / R`, so the `(R−k)` term would treat a
**non-observation** as a Bernoulli failure — silently converting invalidity into
evidence of failure. That is exactly what the rollout protocol forbids for
numerical invalidity and what I37 forbids for infrastructure failure. The event
is retained, but its likelihood is biased toward failure.

### Why this cannot be guessed

B is blocked by frozen authority, so the real choice is A versus C, and they
differ materially: A drops the event entirely; C keeps it with a downward-biased
likelihood. The difference changes both the retained-event count that gate S4
measures and the supervision signal the loss consumes. Building the compiler,
producer, supervision writer and qualification canary on a guessed rule would
produce a production image and a reference semantic digest that the owner's
answer could invalidate.

**Agent recommendation (not a selection): A.** It is the only reading that
neither contradicts a frozen contract nor injects a non-observation into the
likelihood, and it inherits the pair atomicity used since V1. Gate S8 already
bounds how often it can cost an event. Selection authority is the owner's.

**Infrastructure failure remains separate and unaffected.** A required replica
that did not execute because of timeout, worker crash, serialization or transport
failure is not a Bernoulli failure observation and is not scientific invalidity;
it is handled by frozen operational retry and resume.

### What the owner must state

1. The rule for constructing `(k, R)` when a required replica is scientifically invalid.
2. Whether the affected candidate's pair publishes rows.
3. Whether such events count toward the gate S4 retained-event minimum.
4. Which frozen contract records the rule, and which contract hash changes.

## I1 — implementation binding, and a correction to the prompt's hashes

All five frozen V3 contracts verify **exactly** and self-verify:

| Concept | Full SHA-256 |
|---|---|
| Probabilistic target `p(x, τ)` | `a127bf9fbe907c81f2cd8037e94164f738ee756d7480c7db6955d7405bc355b6` |
| Replica protocol, R per family | `6c2143c4782f0d851205cb118a2ff1c3e33c8a6a3e3cdc2ce5a820106551fa9a` |
| Row identity and binding | `bdab65bdabbf503dc4d76d7d66d14c6504feb657b32d153a89643fab55058a8c` |
| Grouped Bernoulli loss | `fc9c093327eaaa5ae95c038cf36a2a16ff2fee6d5fdc125dd1106bc3a99dfc11` |
| Replica-normalized Brier | `0bf6dee325825953d856fb4f6b5df190879424b0d5e8d29cbe55ac930f682f04` |

**Correction.** The phase prompt's abbreviations for the two dry manifests and
the exclusion union name the **outer artifact** hashes, not the **inner manifest
roots**. Both are now recorded in full so machine-readable authority is never
abbreviated or conflated:

| Object | Inner root | Outer artifact hash |
|---|---|---|
| Layout split registry V2 | `5494914e687a306b0288ce416e80d7c8a25f0f79377580eba58edc538d53680a` | `f6e1…` (recorded in artifact) |
| V3 TRAIN dry manifest | `6390cd31570d3dc12040d3522ca77db915171b82a2724db02825a32e90bd6edd` | `ffb1fe33…` (the prompt's value) |
| V3 VALIDATION dry manifest | `431e42ee832c808a6bb9747ee23940d4bb7d18d9b7a5f55bc43fcaa7f4a648f2` | `72f88a62…` (the prompt's value) |
| Exclusion union V2 | `68fc04e11ea5eeeb8d9b1ce099bacb38b0e737d9c00385f0321cb97037a1fb4d` | recorded in artifact |

The registry abbreviation `5494914e…` did refer to the inner root, which is what
made the discrepancy worth stating rather than silently reconciling.

## I28 — dry manifest verification

| Split | Episodes | Layouts | Per layout | Offsets | Executed | Rows |
|---|---|---|---|---|---|---|
| `v3_train` | 1200 | 20 | 60 | `[0.22, 0.54]` | 0 | 0 |
| `v3_validation` | 300 | 10 | 30 | `[0.65]` | 0 | 0 |

Offset `0.33` appears in neither split; it remains `UNUSED_RESERVE`. Dry only —
no generation was performed.

## Historical gate 7 — unchanged

TRAIN F9/LINE remains **59 / 530 = 0.11132075471698114 > 0.10**, status
`FAILED_FOR_V2`. For V3 it is recorded as
`NOT_APPLICABLE_TO_V3_PROBABILISTIC_TARGET` — never as passing, never as
threshold-changed. Nothing in this phase touched it.

## Work completed and work not started

Completed: I0 handoff verification, I1 binding table with full hashes and the
outer/inner correction, the exhaustive I10 authority search, I28 dry manifest
verification, and gate-7 reverification.

Not started, all blocked on the I10 answer: I2–I9 additive implementation;
I11–I17 pair transaction, row binding, writer, loader, loss; I20–I22 Brier;
I26–I27 registry and split guards; I29–I38 qualification canary; I41–I44 image
build and reference qualification; I45–I52 Windows target qualification.

Counters: code written 0, modules created 0, images built 0, official V3 rows 0,
Target V4 evaluations 0, models trained 0, HP trials 0, frozen contracts modified
0, V2 modified 0, gate 7 modified 0, N24 / Study B / final-test accesses 0.

## Artifacts

- `results/rvt_fd24/phase9g_v3i_q_implementation_binding_v1.json`
- `results/rvt_fd24/phase9g_v3i_q_replica_invalidity_owner_decision_v1.json`
- `results/rvt_fd24/phase9g_v3i_q_final_readiness_v1.json`
- `tests/test_phase9g_v3i_q_probabilistic_implementation.py` — 39 tests, all passing

## Next phase

A single owner decision on V3 replica-invalidity semantics, recorded as a frozen
contract, unblocks this phase to run unchanged in every other respect.
