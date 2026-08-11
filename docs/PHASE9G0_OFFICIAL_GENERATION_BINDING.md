# Phase 9G0 Official Generation Binding

## Verdict

**A. Closing the executable binding requires genuinely new scientific
decisions.**

Phase 9G0 stopped at the mandatory provenance-map gate. No official producer,
task compiler, writer, command plan V2, run ID, staging output, scientific row,
shard, model training operation, checkpoint, or optimizer state was created.
Study A N24 and final test were not accessed.

The historical startup Verdict A at commit
`9e3363edae42287b3ad04a039bc1bf495cce58a1` remains unchanged.

## Diff Audit

The complete delta from RB21-TARGET `c4009ec` to the startup-stop commit has two
files. `docs/PHASE9_OFFICIAL_GENERATION_STARTUP_STOP.md` is DOCUMENTATION and
`results/rvt_fd24/phase9_official_generation_startup_block_v1.json` is an
ARTIFACT. There are no scientific-runtime, operational, test, or unexplained
mutations.

## What Is Frozen

The committed tree uniquely defines source episode IDs, dataset cell fields,
four independent source seeds, event IDs and steps, robot IDs, COMPACT/LINE
candidate IDs, replica IDs, Target V4, F8/F9 three-replica all-success
aggregation, and Residual V2 scientific/candidate/supervision identities.

The matched disturbance authority is also complete. `_replica_seeds` derives
`matched_disturbance_seed` from the `counterfactual_rollout` namespace with
`candidate_topology=null`. COMPACT and LINE therefore share the same seed for
one event and replica, while replica index remains in the payload. Worker,
chunk, retry attempt, and execution order are absent. All 21,000 authorized
candidate comparison groups satisfy the pair rule; all 3,000 F8/F9 events have
six jobs, three replica indices, and three distinct matched seeds.

## Three Scientific Levels

The frozen contracts distinguish the following levels:

| Level | Frozen meaning | Identity status |
|---|---|---|
| SOURCE EPISODE | One qualified simulator trajectory in one study/split/family/layout/team-size cell, with four namespace-separated source seeds. | Frozen. |
| LABEL ATOMIC UNIT | One source decision event, one candidate topology, and all required replicas. F1-F7/F10 use one replica; F8/F9 use three and aggregate by `all_success`. | Frozen independently for each candidate. |
| TRAINING ROW | One robot-local, candidate-conditioned ego graph carrying the aggregate recoverability target. A valid matched candidate pair has planned multiplicity `2*N`. | Multiplicity is frozen; graph binding and scientific row identity are not. |

The candidate aggregate is therefore not a global training row. The intended
mapping is source event -> candidate replica aggregate -> robot-local rows. It
cannot be materialized officially because the final arrow lacks the frozen
graph-content and row-identity derivations described below. No canary row count
is claimed or inferred from benchmark counters.

Residual supervision uses a different frozen identity chain: attempted state
-> nine candidate evaluations -> one LABELED row, or an audit-only frozen
disposition such as `NO_ELIGIBLE_ACTION`. The identity chain is frozen, but the
authoritative attempted-state universe is not.

## Missing Scientific Derivations

The frozen V1 local-view label dataclass specifies recoverability label fields,
but it does not include an actual ego-graph fingerprint/content reference or a
scientific row ID. The repository has no recoverability row-identity artifact
or function. Hashing the complete label would put the outcome in identity;
choosing a subset would define a new identity scheme. Neither is authorized.

The counterfactual trace schema requires `rollout_configuration_sha256`,
`source_lifecycle_sha256`, and `communication_condition_sha256`. The official
runtime never defines their canonical preimages. Only a synthetic Phase-8
diagnostic constructs one example rollout-configuration document.

Recoverability row emission is paired: `joint_outcome_category` and the invalid
pair policy require both candidate aggregates. The operational unit is one
candidate with all replicas. No frozen transaction identity or reconciliation
rule defines how two independently scheduled atomic results become one paired
robot-row set.

Residual row identity and the nine-candidate expert are frozen, but task
compilation is not. The budget fixes a per-cell quota and hash ranking. It does
not uniquely enumerate legitimate dense states or specify deterministic
enforcement of the frozen maximum 64 retained timesteps per episode. Different
reasonable enumerations select different scientific rows.

These are dataset-content and identity choices, not task scheduling or writer
overhead. Implementing them would violate the 9G0 rule against inventing a
default.

## Blocker Classification

The original four startup blockers remain valid:

1. Command plan V1 is selector-only.
2. RB21 qualifies a diagnostic path, not an F1-F10/Study B N24 producer.
3. The diagnostic path does not emit robot-candidate recoverability rows.
4. Its disturbance binding uses the source dynamic-obstacle seed instead of
   the frozen candidate-replica matched seed.

Phase 9G0 resolves the authority for blocker 4 but cannot close blockers 1-3
without the missing row and task-universe decisions above.

## Downstream Gate Status

Because the mandatory 9G0-2 map failed closed, no F1-F10 dispatcher, Study B
N24 producer support, official task compiler, canonical writer, diagnostic
producer mode, structural canary, RB20-through-official-path replay, command
plan V2, or production-path timing qualification was created. Existing
manifest scope and seals remain intact, but they do not constitute executable
official-producer qualification. The Study A N24 and final-test gates were
observed only through existing guard tests; their scientific contents were not
enumerated or opened.

The RB21 diagnostic profile (`W=12`, one numeric thread per worker, chunk one,
1200-second infrastructure timeout) is consequently
`NOT_EVALUATED_NO_OFFICIAL_PRODUCER`, not inherited and not rejected on
performance evidence.

## Required Amendment

A pre-data scientific amendment must freeze:

- the recoverability row identity and graph payload/content reference;
- canonical preimages for the three required rollout trace hashes;
- the paired candidate aggregate-to-row transaction and invalid-pair commit;
- the exact residual dense-state candidate universe and per-episode retention
  algorithm.

After approval, a later additive binding phase can implement the official
producer, F1-F10/Study B support, canonical writer, dry-run canary, command plan
V2, negative preflight, replay, and production-path qualification.

## Isolation

All official and sealed-domain counters remain zero. The RB21 W12, thread-1,
chunk-1, 1200-second profile is not inherited by a nonexistent official
producer and remains `NOT_EVALUATED_NO_OFFICIAL_PRODUCER`.

## Verification

- Phase 9G0 fail-closed artifact tests: 5 passed.
- Focused generation, identity, retry, locality, RB20, RB21P, and RB21 contract
  regression: 201 passed.
- Existing RB21 canonical validator: PASS; 15 negative cases, zero escapes.
- Complete local suite: 3007 passed, zero failed, zero xfailed; one pre-existing
  PyTorch conversion warning.

Official-command dry resolution and official-path semantic replay are not
applicable: Verdict A prohibits creating the executable command plan and
producer they would exercise.
