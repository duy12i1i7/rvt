# Phase 9C-RB21 Operational Qualification

## Verdict

**D. Operational qualification remains incomplete or the target environment is
not qualified.**

The current machine is the same macOS development environment used for RB-20,
but no owner-declared official generation environment identity or equivalence
proof exists. RB-21 therefore does not select a worker count, chunk size,
timeout or throughput commitment and does not authorize any official scope.

No scientific semantics were changed. No official generation or training ran.

## Identity

- Scientific source commit: `297a94b9a7e951b9b30b14befca16a92d9c1189e`.
- Branch: `research/rvt-rb21-operational-qualification-v1`.
- RB-19 current provenance root:
  `e8317ad3e9facc76511098503cdad55dfc065dedd8fc2b530a2b25845c3f5571`.
- RB-20 reproduction:
  `8c55f4ef40be509dc6e0bc678467873e5ebd0ce60d0195a2227555676114b95a`.
- Target V4:
  `54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee`.
- RB-21 evidence commit: recorded after final verification.
- Baseline inherited from the handoff: 2946 passed, 0 failed, 0 xfailed,
  0 xpassed. It was not rerun merely to restate the baseline.

## Takeover Audit

The requested first inspection found a clean worktree already on the RB-21
branch at the exact RB-20 source commit. The annotated tag
`rvt-rb20-clean-repro-pass-v1` already existed and dereferenced exactly to that
commit, so it was not moved.

The handoff described uncommitted `rb21_manifest.py`, `rb21_units.py` and
`rb21_bench.py` files. None existed in the worktree, any registered worktree or
the searched user/temp paths; `git status`, unstaged diff and staged diff were
empty. Therefore:

- inherited `rb21_manifest.py`: absent;
- inherited `rb21_units.py`: absent;
- inherited `rb21_bench.py`: absent;
- other inherited RB-21 changes: none found;
- discarded predecessor work: none;
- production operational code inherited: none;
- syntax/import failures inherited: not applicable.

The implementation added the corresponding modules under
`rvt_swarm/phase9c_rb21/`. It reuses the qualified scientific executor,
Residual Expert V2, Target V4 evaluator, identity contracts and RB-19/RB-20
preflight evidence rather than reproducing their equations.

## Target Environment

Current diagnostic host:

| Field | Observed |
|---|---|
| Identity | `udy-2.local:Darwin:arm64` |
| OS | macOS 26.5 / Darwin 25.5.0 |
| CPU | Apple M4 Pro |
| Physical / logical cores | 12 / 12 |
| RAM | 25,769,803,776 bytes |
| Workspace filesystem | local APFS; about 68 GB available at final measurement |
| Temporary storage | local `/tmp` mapping on the same data volume |
| Python | 3.9.6 |
| torch | 2.8.0 |
| numpy | 2.0.2 |
| multiprocessing | `spawn`, `fork`, `forkserver` available; harness uses `spawn` |
| scheduler/container | none detected |

Qualification result: `TARGET_ENVIRONMENT_NOT_QUALIFIED`. The environment
artifact hash is
`e6ad3dd1ebc3d36593252bf658dcab41e5f42261034a4a7d416ef1180f1d4b3c`.

## Work Units

Residual atomicity is one expert decision for one robot containing candidate
indices 0 through 8. Construction and scheduler checks reject every subset.
One worker executes all nine continuations, the frozen selector and Target
builder before returning the unit.

Recoverability atomicity is one decision state times one candidate topology.
It contains one replica for ordinary families and all three replicas for F8/F9
before aggregation. Scheduler-level candidate and replica splitting are
rejected. Parallelism is only across complete independent units.

Every worker receives `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`,
`OPENBLAS_NUM_THREADS=1`, `torch_num_threads=1` and
`torch_num_interop_threads=1`.

## Benchmark Manifest

The canonical manifest was written before timing. It contains 32 complete
residual units (288 candidate evaluations) and 32 complete recoverability units
(64 replica rollouts). It covers train and validation only, families F1, F5,
F8 and F9, and N in {5, 8, 12, 16}. It includes structural cases for early and
long continuations, topology change, dynamic obstacles, degraded
communication, labeled residual states and the naturally available F5
no-eligible state.

Median, p90, p95 and empirical maximum are declared. P99 is explicitly not
reported. The manifest hash is
`4ac5bd1d00c6d2a1e0a71a712c98577e3e866066001802948b5cf3ecb3104ead`.

The full manifest was not run because G1 failed before performance selection.
This is intentional: insufficient target coverage is a hard-stop reason for
Verdict D, not permission to extrapolate.

## Diagnostic Timing

One non-authorizing smoke used the same four complete units in both
configurations:

| W / chunk | Wall (s) | Units/s | Speedup | Efficiency | Peak worker RSS |
|---|---:|---:|---:|---:|---:|
| 1 / 1 | 18.17 | 0.2201 | 1.000 | 1.000 | 189 MB |
| 2 / 2 | 14.02 | 0.2852 | 1.296 | 0.648 | 377 MB |

For W=1, residual atomic-unit time had count 2, median 6.49 s and maximum
10.88 s. The 18 candidate continuations had mean 0.668 s, median 0.588 s, p90
1.444 s, p95/max 1.522 s and at most 75 control intervals. Selector/target
reduction was 0.00402 s median and serialization 0.0000474 s median. The two
units produced one `LABELED` and one `NO_ELIGIBLE_ACTION` disposition.

Recoverability atomic-unit time had count 2, median 2.285 s and maximum 3.588 s.
The two replica rollouts had median 1.769 s, maximum 2.611 s and at most 164 control
steps. Aggregation and serialization were each below 0.00001 s.

These counts do not support production percentiles or p99. Exact timing values
and inherited RB-15 distributions are in the performance artifact.

## Semantic Equality

Both actual performance configurations produced the exact semantic digest:

`ddfc1ef5a2534d5a4c7d4fbf415ec7dcae890375bd8d01b0c1069770bab7f5de`

The projection excludes only worker, chunk, attempt, process, timing, memory and
serialization metadata. Scientific identities, snapshots, streams, raw
predicates, candidate records, utilities, dispositions, labels and WORLD
targets remain included. The earlier RB-20 fixture projection independently
passes the same metadata-invariance check.

This passes G2 only for the diagnostic task set. There is no selected production
configuration to compare.

## Chunking and Timeout

Predeclared diagnostic chunks are 1, 2, 4 and 8 complete units. Only chunks 1
and 2 were smoke-tested. No chunk is selected. The future selection rule weighs
throughput, p95 latency, RAM, load balance, retry blast radius and resume
granularity, preferring the smaller chunk when throughput is near-equal.

No timeout is selected. The historical residual value 1800 s remains recorded
as non-authoritative. The harness maps an operational deadline only to
`INFRASTRUCTURE_FAILURE`; it does not pass it into the simulator, shorten the
counterfactual horizon, evaluate Target V4 from the deadline or emit a row.
Semantic retries remain 0 and the frozen infrastructure retry limit remains 1.

## Storage

Measured canonical sizes were:

| Payload | Bytes |
|---|---:|
| Recoverability scientific record | 438 |
| Recoverability replica/audit metadata | 1,202 |
| Residual labeled row | 5,902 |
| Residual nine-candidate sidecar | 4,196 |
| NO_ELIGIBLE_ACTION audit record | 5,901 |
| Sample shard/index/manifest metadata | 322 |

The conservative projection is 3.31 GB scientific payload, 5.81 GB audit
sidecars, 9.58 GB final dataset, 9.58 GB staging, 2.39 GB temporary data and
21.74 GB for staging + final + temporary + resume metadata. Current diagnostic
storage has about 3.1x this bound. This does not qualify the unknown target.

The unchanged canonical JSON writer measured about 680 record transactions/s
and 6.88 MB/s over 200 fsync-backed diagnostic commits. No compression or
scientific encoding change was introduced.

## Resume and Failure Safety

Completion is indexed by atomic scientific unit identity. A unit is complete
only after record and sidecar hashes match an atomic commit manifest. Restart
rescans those identities, not chunk positions. Exact duplicate submission is
idempotent; the same identity with changed content is rejected.

Injected failures after record write, after sidecar write and before promotion
were never accepted as complete. Insufficient temporary space was rejected
before commit. Attempt state remained in the diagnostic attempt journal. The
same transaction path preserves `NO_ELIGIBLE_ACTION` without a target row.

These helpers pass on the local diagnostic filesystem; target-filesystem and
machine-interruption qualification remain pending.

## Capacity and H4

No target throughput exists, so recoverability wall time, Residual V2 wall
time, CPU-hours, target peak RAM and candidate evaluations/s remain
`PENDING_TARGET_ENVIRONMENT`. The frozen residual scale remains at most 536,000
stored rows and 4,824,000 candidate evaluations; the latter is not a row count.

The required exact H4 label is
`H4_OPERATIONAL_RISK_BUT_FEASIBLE`, scoped explicitly as a **provisional,
non-authorizing diagnostic classification**. Existing measurements show finite
execution without hangs, but target worker/timeout/capacity evidence is absent.
The residual branch therefore stays disabled and unauthorized. This
classification must be recomputed from the predeclared criteria on the actual
target; it is not a production conclusion.

## Authorization

| Scope | Status |
|---|---|
| RECOVERABILITY_GENERATION | NOT_AUTHORIZED_TARGET_ENVIRONMENT_PENDING |
| RESIDUAL_V2_GENERATION | NOT_AUTHORIZED_TARGET_ENVIRONMENT_AND_H4_PENDING |
| STUDY_A_TRAIN_VALIDATION | NOT_AUTHORIZED |
| STUDY_A_N24_ZERO_SHOT | SEALED_NOT_AUTHORIZED |
| STUDY_B | NOT_AUTHORIZED |
| FINAL_TEST | SEALED_NOT_AUTHORIZED |

No broad `generation_authorized=true` state exists.

## Artifacts and Preflight

Key hashes at the evidence run:

- operational contract:
  `41c9f2399b2c214c2d49cac7f9ac99d60a9679dfb75bdd1580a1e49d79fc1e5a`;
- operational job manifest:
  `f7eb010872d75f685decfc9cc9647a360490fb1876fc3a2f97e04202c3349efd`;
- readiness root:
  `1de91fd787a875e0a973bc66567b404fa5a3343b8fc915ac40696e4960c6ff21`.

Scientific preflight passes with no failed checks. Operational preflight is
blocked only by target environment, worker count, chunk size and timeout. All
13 negative cases are rejected, including stale roots, oversubscription,
unsafe writer mode, broken seals and broad authorization.

## Command Plan

The exact qualification command is prepared and was executed only in the
diagnostic namespace:

```bash
env PYTHONPATH=. .venv/bin/python scripts/run_phase9c_rb21_qualification.py --run-diagnostic-benchmark
```

An official generation command cannot be made deterministic while worker,
chunk and timeout are pending. Therefore no executable official command was
created. No Study A N=24 or final-test command exists. After target
qualification, a new versioned operational contract and job manifest must pin
those values before an owner can authorize an exact staging command.

## Isolation

- final-test runtime accesses: 0;
- Study A N=24 runtime accesses: 0;
- official recoverability rows: 0;
- official residual rows: 0;
- official scientific shards: 0;
- new FD24 checkpoints: 0;
- optimizer states: 0;
- training operations: 0.

Official Phase-9 scientific generation is **not operationally authorized**.
