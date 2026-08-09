# Phase 9C-RB18 — Structural Generation Canary

**Result: both label branches execute end to end with zero official data.
Verdict C.**

RB-18 runs the real publication machinery — source episodes, recoverability
candidate rollouts through Target V4, and Residual Expert V2's nine candidates —
through the RB-17 generation contract, and checks that identities, dispositions,
frame context and serialization all survive.

Canary artifact `rb18_structural_generation_canary_v1.json`, hash
`0291cb52e11e570f48272d76b98d32966513fc8f840a6e47e718076bf3187e3c`.

## What this is not

RB-18 **does not** estimate class balance, H2 effect size, model performance,
dataset statistics or training feasibility. **No sample generated here belongs to
any train or validation dataset** — every record is stamped
`RUNTIME_CONFORMANCE_ONLY` and `SCIENTIFIC_DATASET = false`, and everything lives
under `results/rvt_fd24/rb18_canary/`. Study A N=24 and the final-test split
remain sealed and untouched. The official generation timeout remains unresolved
and official Phase-9 generation remains unauthorized.

## Finding: the RB-17 root does not reach Target V4

RB18-0 resolves the RB-17 composite before executing anything. Twelve of the
thirteen required references resolve — scientific protocol, ET timing, headroom
authority, Residual Expert V2, RB-15 binding, WORLD model repair, runtime
composite, all three identity contracts, disposition contract, supervision-row
schema, budget V2 and manifest V2.

**The Target V4 execution contract is cited nowhere in the chain**, even though it
governs the entire recoverability branch this canary exercises. RB-18 binds it
additively in its own artifact (`54a0e0baff79…`, the same value headroom v6
records) and reports the gap; the RB-17 composite is **not** rewritten. Closing it
properly is an owner decision for RB-19.

## Predeclared cases

Fixed before execution, never chosen after seeing outputs:

| case | layout | family | N | policy | role |
|---|---|---|---:|---|---|
| c1 | `train-f1-00` | F1 | 6 | S1 | no changed-topology event; small N |
| c2 | `train-f9-00` | F9 | 12 | S0 | dynamic obstacle; changed-topology events; larger non-N24 N; 3 replicas |
| c3 | `validation-f8-00` | F8 | 5 | S1 | communication-degraded; 3 replicas |
| c4 | `train-f5-00` | F5 | 8 | S1 | transition-heavy; the qualified all-nine-infeasible state |

No geometry or timing was edited to force any outcome.

## Results

**Source** — 4 episodes, 2 scheduled decision events, 1 observed changed-topology
event, 0 unreachable through early termination, no schedule mutation.

**Recoverability** — 3 decision states, both topology candidates each, **14
candidate rollouts** (F1 → 1 replica, F8 and F9 → 3 matched replicas each, as the
frozen rule requires). 4 positive and 2 negative aggregate labels, 0
execution-invalid. At least one replica created a changed-topology lifecycle and
ran the qualified transition stack. Raw termination causes are preserved
alongside — never collapsed into — the Target V4 disposition. A rerun is
bit-identical.

**Residual** — 4 attempted expert states, **3 LABELED**, **1
NO_ELIGIBLE_ACTION**, 0 execution-invalid, **36 candidate evaluations** (nine per
state, no subset, no fast path), 3 prospective rows. The no-eligible state emits
zero rows, keeps its nine evaluation identities as audit evidence, and still
counts in the denominator — so rows (3) are legitimately fewer than attempted
states (4).

## Schema, identity and execution

Every labeled row round-trips exactly: orientation, node tensor, edge tensor,
edge index and candidate/topology context all identical after serialize →
deserialize → loader, and the deterministic untrained model returns **identical
residual outputs and identical recoverability logits**. A non-symmetric mixed-sign
WORLD target `(0.075, −0.0375)` survives the writer path with x, y, sign, scale
and frame intact and no rotation.

Scientific row ids never contain a candidate index; all nine candidate ids per
state are distinct; the three residual namespaces and the recoverability
evaluation namespace do not collide anywhere. Two different scheduling partitions
produced identical scientific output after canonical sort while the execution ids
differed, an infrastructure retry changed only execution metadata, and reruns are
bit-identical down to the sidecar and the prospective row hash.

The dry-run writer used the official canonical encoder, read every record back
exactly, wrote nothing under an official shard path, and peaked at 1,465 bytes
per row.

## Preflight

Preflight passes before and after the canary, and still rejects the mission-frame
model declaration, a missing orientation field, a row identity admitting
`candidate_index`, the historical 1800 s timeout presented as authoritative,
augmentation re-enabled, and an unknown disposition vocabulary. No negative guard
was weakened to make the canary run.

## Timing — observability only

Canary wall clock and per-decision residual timings are recorded for
observability. **No operational decision was made**: worker count, chunk size,
job timeout and cluster size all remain RB-21's to choose, and the budget still
reads `PENDING_RB21_PERFORMANCE_QUALIFICATION`.

## Official counters

Scientific rows persisted **0** · scientific shards **0** · checkpoints **0** ·
optimizer states **0** · final-test accesses **0** · Study A N=24 accesses **0**.
