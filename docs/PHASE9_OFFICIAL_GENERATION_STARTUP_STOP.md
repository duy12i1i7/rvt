# Phase 9 Official Generation Startup Stop

## Verdict

**A. Official generation exposed a new scientific specification problem.**

No official run identity was created, STAGING was not touched, and no target
host generation command was launched. Recoverability rows, residual rows,
scientific shards, training operations, checkpoints, optimizer states, Study A
N24 accesses, and final-test accesses all remain zero for this task.

Machine-readable evidence is recorded in
`results/rvt_fd24/phase9_official_generation_startup_block_v1.json`.

## Preconditions

The audit began from clean HEAD
`c4009ecadbca3c2c4ce30a30c2f90278ae5184fc` on
`research/rvt-rb21-target-performance-v1`. The committed RB21-TARGET artifact
validator passed, including the exact operational contract, job manifest,
command plan, readiness root, 15 negative preflight cases with zero escapes,
and zero sealed-domain accesses. The focused operational evidence suite passed
25 tests.

The owner authorization is present for Recoverability, Residual V2, Study A
train/validation, and Study B. Study A N24 and final test remain sealed.

## Blocking Finding

The committed command plan contains eight immutable selectors but no executable
commands. It explicitly defers binding those selectors to a qualified Phase-9
generator. No such official generator exists in the qualified image or the
evidence commit.

The available RB21 implementation is a diagnostic benchmark, not an official
producer:

- `DiagnosticCase` rejects N24 and every family outside F1, F5, F8, and F9,
  while the authorized Study B scope includes N24 and the manifest covers
  F1-F10.
- The recoverability benchmark returns one aggregate label and replica traces.
  It does not emit the required robot-candidate records or serialized
  robot-local ego graphs.
- The benchmark binds counterfactual disturbance to the source dynamic-obstacle
  seed, not the candidate-replica `matched_disturbance_seed` frozen in the job
  manifest.
- The recoverability loader enforces several provenance and grouping guards but
  there is no canonical recoverability-row identity/serializer comparable to
  the frozen Residual V2 row identity.
- `AtomicUnitStore` can atomically persist arbitrary record/sidecar mappings,
  but no qualified producer defines their official schemas, shard/index
  construction, denominator reconciliation, or final dataset manifest.

The exact qualified image is sourced from commit
`8bfabd48969f1fa1e13a0a268a6df1cb366e90cc`. Its Phase-9 files contain the same
diagnostic benchmark and schema-agnostic store, with no official producer.
Commits through `c4009ec` add target benchmarks, operational probes,
orchestration, preflight, and readiness evidence; they do not add an official
dataset generator.

## Why Execution Stopped

Constructing a generator during this authorized run would require choosing
scientifically observable bytes and identities: robot-level row construction,
ego-graph serialization, matched-seed mapping, event-unreachable records,
disposition records, and shard/index schemas. Those choices affect dataset
content and cannot be inferred from worker/chunk/timeout qualification.

Using the benchmark as a substitute would also exclude authorized families and
Study B N24 and would use the wrong disturbance seed binding. That would violate
the command-plan requirement and the no-improvisation rule.

## Frozen Scope Accounting

Excluding sealed Study A N24, the manifest authorizes 3,060 source episodes,
15,000 decision-event slots, 30,000 recoverability atomic units, 42,000
candidate-replica rollouts, and capacity for 318,500 robot-candidate rows. None
were started.

The sealed Study A N24 allocation remains 60 source episodes, 300 events, 840
replica rollouts, and capacity for 14,400 rows. It was not materialized or
accessed.

## Required Repair

A separate pre-data repair must freeze and qualify the official
manifest-to-producer binding. It must cover all authorized families and Study B
N24, preserve candidate-replica matched seeds and F8/F9 aggregation, define
canonical recoverability rows and ego-graph payloads, define unreachable-event
and disposition accounting, and define shard/index/audit/finalization schemas.

Only after that producer passes exact-image semantic, resume, writer, seal, and
W12 operational qualification can the current authorization be exercised
without inventing science during generation.
