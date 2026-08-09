# Phase 9C-RB21 Generation Runbook

## Current State

This runbook is blocked at target-environment qualification. Do not execute
official generation from the current contract. Worker count, both chunk sizes
and timeout are `PENDING_TARGET_ENVIRONMENT`.

## Preconditions

1. Use the owner-declared official generation host or a documented equivalent.
2. Checkout the eventual clean RB-21 evidence commit.
3. Verify the RB-20 tag dereferences to
   `297a94b9a7e951b9b30b14befca16a92d9c1189e`.
4. Keep `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, torch
   compute threads and torch interop threads at the versioned contract values.
5. Confirm Study A N=24 and final test remain sealed.

## Qualification

Run the benchmark manifest unchanged on the target. Measure W=1 first, then the
predeclared worker and chunk matrices. Require identical semantic digests for
every configuration. Reject swap-dependent or low-headroom worker counts.

Select chunk sizes using throughput, p95 tail, memory, load balance, retry cost
and resume granularity. Prefer the smaller chunk for near-equal throughput.
Derive timeout from the selected chunks, observed tail, maximum scientific
workload and writer finalization. Never use timeout as a scientific horizon.

## Preflight

The positive preflight must pass both scientific and operational checks. Abort
on a stale RB-19 root, missing RB-20 reproduction, target mismatch, worker or
thread mismatch, wrong chunks, stale timeout, missing resume contract, direct
final writes, broken seals, or unauthorized scope.

## Execution Shape

- Residual: one worker owns one robot decision and all nine candidates.
- Recoverability: one worker owns one decision/candidate and every frozen
  replica; F8/F9 use all three.
- Semantic retry: 0.
- Infrastructure retry: at most 1 with identical scientific identity and
  inputs.
- Begin only in a versioned STAGING namespace.

No official command is present in RB-21 Verdict D. A later target-qualified job
manifest must supply an exact version-pinned command for each authorized study,
split and label branch. It must not contain Study A N=24 or final-test commands
while their seals remain closed.

## Resume

On restart, scan validated atomic unit commit manifests. Do not infer completion
from chunk positions. Replay incomplete units exactly. Treat exact duplicate
submissions as idempotent and reject identity/content conflicts.

## Monitoring

Track scheduled, started, acknowledged, retrying and failed atomic units;
throughput by branch; median/p95 latency; worker/coordinator RSS; temporary and
final storage; writer queue depth; duplicate identities; hash failures; and
sealed-domain access counters.

## Failure Handling

An operational timeout, worker death, process interruption or temporary storage
failure is `INFRASTRUCTURE_FAILURE`. It cannot create a task-negative label.
Abort the run on semantic digest drift, corrupted commits, unresolved failures,
unexpected duplicates, insufficient storage headroom or any seal violation.

Do not increase retries to compensate for a bad timeout. Do not alter frozen
science to improve throughput.

## Completion and Promotion

A run is complete only when every scheduled source task is accounted for, every
legitimate attempted unit has a terminal disposition, infrastructure failures
are resolved, denominator counts reconcile, duplicates are resolved, all
record/sidecar/shard/index hashes validate and sealed-domain counters remain
zero.

Only then write the completion manifest and atomically promote STAGING to FINAL.
Partial staging is never a finished scientific dataset.

## Abort Procedure

1. Stop scheduling new chunks.
2. Allow acknowledged atomic commits to finish; never expose staging as final.
3. Record active attempts as interrupted infrastructure failures.
4. Preserve staging, attempt journals and monitoring logs for exact resume.
5. Re-run preflight and hash validation before resuming.
6. Require owner action before any new official authorization.
