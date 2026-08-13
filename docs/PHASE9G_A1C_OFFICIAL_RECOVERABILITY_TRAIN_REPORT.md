# Phase 9G-A1C Official Recoverability TRAIN Report

## Status and verdict

Study-A Recoverability TRAIN completed, reconciled, independently validated, and finalized. Recoverability validation was not started.

**Verdict C. Study-A Recoverability TRAIN completed, reconciled and finalized successfully; validation may be separately authorized.**

## Identity

- Evidence commit at authorization: `af5c083e58476f5bd8a08710ce567176108e8f06`
- Authority commit: `869db24fac87b24b60a95fd192a6a75a63fc0ed0`
- Startup requalification commit: `982349d92863a0a3c5a6bcdce25332877df27be0`
- Executable image source: `848e8b352a91e95af777ebbeccd5fbb43d53777e`
- Target image: `sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90`
- Authorization continuation: `6bb55ef39de6f78a81ced45e9bfa960daf72acb650e432e690a16e019a61e2ae`
- Run ID: `phase9g-a1c-study-a-train-recoverability-continuation-20260813T112333Z`
- Parent run ID: `phase9g-a1r-study-a-train-validation-recoverability-continuation-20260812T061720Z`

## Prestart

- Initial events: 210
- Initial rows: 342
- Checkpoint: `72cde9c6923f7eba0e6cbc9d18cb44d68fde7933a65907ad5501cf893df3001f` (exact)
- Duplicate identities: 0
- Partial transactions: 0
- Remaining-manifest S3 unresolved ambiguities: 0
- Qualified profile: W=12, numeric threads=1, chunk=1, timeout=243 s

The first launch exited before scientific execution because `/opt/rvt` selected the image copy of an operational helper. Attempt 1 wrote 0 transactions and 0 rows. The launch binding was requalified with working directory `/a1c`; no wrapper bytes, source image, profile, authorization, or scientific semantics changed.

## TRAIN execution

| Metric | Result |
| --- | ---: |
| Source episodes | 1,200 |
| Decision events | 6,000 |
| Candidate aggregates | 12,000 |
| Replica executions | 1,094 |
| RECOVERABLE_POSITIVE | 532 |
| VALID_TASK_NEGATIVE | 354 |
| GENERATION_INVALID | 11,114 |
| Candidate pairs retained | 443 |
| Candidate pairs dropped/nonpublished | 5,557 |
| Robot-local scientific rows | 8,340 |
| A1C infrastructure timeouts | 0 |
| Historical pre-A1C infrastructure timeouts | 2 |
| Scientific retries | 0 |
| Writer failures | 0 |
| Duplicates | 0 |
| Partial transactions | 0 |
| A1C wall time | 2891.102 s |
| Accumulated observed lineage wall time | 3381.310 s |
| A1C candidate CPU time | 8.087065 CPU-hours |
| Accumulated sampled CPU time | 9.108527 CPU-hours |
| Maximum atomic-unit wall time | 67.674 s |

## S3 counter levels

These denominators are intentionally not pooled:

- Complete TRAIN S3 source instances: 200
- Complete TRAIN S3 decision events: 1000
- Complete TRAIN S3 candidate aggregates: 2000
- Remaining-manifest source instances carried through continuation status: 194
- Robot-local S3 guard observations: 1766
- Participating support observations: 3921
- CENTERLINE_NEUTRAL support observations: 2
- Resolved opposing-pair robot observations: 248
- Existing HOLD_UNKNOWN robot observations: 1518
- Existing source-invalid instances: 4
- Unresolved S3 ambiguities: 0

Complete TRAIN S3 has 45 retained and 955 dropped/nonpublished candidate pairs.

## Existing data lineage

All 342 original rows were retained byte-for-byte and none were regenerated: 254 `UNAFFECTED`, 88 `DEPENDENCY_PRESENT_BUT_VALUE_VALID`, 0 `POTENTIALLY_AFFECTED`, and 0 `PROVEN_AFFECTED`.

## Integrity

All 6,000 transaction hashes, 8,340 row identities, graph fingerprints, matched seeds, candidate-pair boundaries, shard hashes, indexes, and hard-link provenance passed. Unresolved tasks, partial publications, duplicate identities, hash failures, schema failures, seed mismatches, and seal violations are all zero.

The frozen invalid-reason distribution is 3,517 `SOURCE_TERMINATED_BEFORE_EVENT:COLLISION`, 1,920 `SOURCE_TERMINATED_BEFORE_EVENT:GOAL_COMPLETE`, and 120 `SOURCE_TERMINATED_BEFORE_EVENT:INITIALIZATION_INVALID` events. These sum to the 5,557 dropped/nonpublished pairs.

## Dataset

- Dataset ID: `phase9g-a1-study-a-train-recoverability-v1`
- Rows: 8,340
- Transactions/audit sidecars: 6,000
- Shards: 5 (`2048, 2048, 2048, 2048, 148` rows)
- Storage: 248,814,238 bytes
- Manifest: `4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf`
- Seal: `5b9e6726b548722ee651eefa7106662e2b119147d9b0c31ec4d4cbe0a1de58f5`
- Independent validation: `ae67a6d1856e74e45685bc898341877afec83a7c9396c21406df81a4f8457e13`
- Class weighting: `NOT_SELECTED`

## Descriptive distribution

### By family

| Family | Positive | Negative | Invalid | Pairs retained | Pairs dropped |
| --- | --- | --- | --- | --- | --- |
| F1 | 191 | 83 | 926 | 137 | 463 |
| F10 | 13 | 47 | 1140 | 30 | 570 |
| F2 | 41 | 39 | 1120 | 40 | 560 |
| F3 | 0 | 14 | 1186 | 7 | 593 |
| F4 | 0 | 0 | 1200 | 0 | 600 |
| F5 | 29 | 21 | 1150 | 25 | 575 |
| F6 | 0 | 64 | 1136 | 32 | 568 |
| F7 | 190 | 50 | 960 | 120 | 480 |
| F8 | 9 | 11 | 1180 | 10 | 590 |
| F9 | 59 | 25 | 1116 | 42 | 558 |

### By team size

| N | Positive | Negative | Invalid | Pairs retained | Pairs dropped |
| --- | --- | --- | --- | --- | --- |
| 12 | 92 | 54 | 2254 | 73 | 1127 |
| 16 | 62 | 136 | 2202 | 99 | 1101 |
| 5 | 130 | 50 | 2220 | 90 | 1110 |
| 6 | 128 | 60 | 2212 | 94 | 1106 |
| 8 | 120 | 54 | 2226 | 87 | 1113 |

### By candidate topology

| Topology | Positive | Negative | Invalid |
| --- | --- | --- | --- |
| COMPACT | 237 | 206 | 5557 |
| LINE | 295 | 148 | 5557 |

The full family x N x source class x candidate topology cross-breakdown is canonical artifact `374849cc99d08ed9a6f90e95169fdf574f130fa09780ead03a707787376f2658`. No sampling, threshold, Target V4, scenario-count, or class-weighting decision was made.

## Tests and sealed domains

- Prestart complete suite: 3132 passed, 0 failed
- Postrun complete suite: 3136 passed, 0 failed
- Independent dataset validator: PASS
- Study A N24 accesses: 0
- Study B accesses: 0
- Final-test accesses: 0
- Recoverability validation started: NO
- Residual V2 started: NO
- Training operations: 0
- Checkpoints: 0
- Optimizer states: 0

Phase 9G-A1C stops here. Validation requires separate owner authorization.
