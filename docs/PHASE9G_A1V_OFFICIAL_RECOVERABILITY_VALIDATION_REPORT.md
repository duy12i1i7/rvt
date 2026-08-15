# Phase 9G-A1V Official Recoverability VALIDATION Report

## Status and verdict

Study-A Recoverability VALIDATION completed, reconciled, independently validated, and finalized. The immutable TRAIN and VALIDATION datasets are referenced by a sealed combined root.

**Verdict C. Study-A Recoverability TRAIN and VALIDATION are finalized and reconciled; the complete Recoverability dataset is ready for the explicit pre-training coverage/class-weight decision phase.**

## Identity and profile

- Authority commit: `b5e5de5`
- Official run ID: `phase9g-a1v-study-a-validation-recoverability-20260815T163005Z`
- Production image: `sha256:8e26da918841eb146529bbb4ff95f3a55acf9793dcbc534f44dce0700d183a90`
- Profile: W=12, numeric threads=1, chunk=1, timeout=243 s
- Container: exit 0, network none, read-only root filesystem

## TRAIN

- Events: 6,000
- Candidate aggregates: 12,000
- Positive / negative / invalid: 532 / 354 / 11,114
- Retained / dropped candidate pairs: 443 / 5,557
- Scientific rows: 8,340
- Manifest: `4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf`
- Seal: `5b9e6726b548722ee651eefa7106662e2b119147d9b0c31ec4d4cbe0a1de58f5`

## VALIDATION

- Authoritative scheduled and completed events: 1,500 / 1,500
- Candidate aggregates: 3,000
- Replica executions: 316
- Positive / negative / invalid: 154 / 86 / 2,760
- Retained / dropped candidate pairs: 120 / 1,380
- Scientific rows: 2,294
- Timeouts / retries / failures / duplicates / partial publications: 0 / 0 / 0 / 0 / 0
- Wall time: 949.181 s
- Candidate CPU time: 2.525311 CPU-hours
- Manifest: `c991aa3016b38b524a14d9b7037b63d97c2cbbb7d92279fc5a297b9c55d4989e`
- Seal: `c7583b124c573c52b57cd91dc1b54aff8fc02b33cf0a15d5449936a8d540637f`

The exact equations are `154 + 86 + 2760 = 3000` and `120 + 1380 = 1500`. Published rows were reconciled per event using its actual N.

## Coverage

Overall descriptive classification: `COVERAGE_STRUCTURALLY_MISSING`. This warning does not redefine scientific validity and no repair was made.

### TRAIN by family

| Family | Events | Retained | Positive | Negative | Invalid | Rows | Flags |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | 600 | 137 | 191 | 83 | 926 | 2776 | [] |
| F2 | 600 | 40 | 41 | 39 | 1120 | 628 | ['MISSING_RETAINED_N_COVERAGE'] |
| F3 | 600 | 7 | 0 | 14 | 1186 | 88 | ['ONLY_ONE_OR_ZERO_TARGET_CLASSES', 'MISSING_RETAINED_N_COVERAGE'] |
| F4 | 600 | 0 | 0 | 0 | 1200 | 0 | ['ZERO_RETAINED_PAIRS', 'ONLY_ONE_OR_ZERO_TARGET_CLASSES', 'MISSING_RETAINED_N_COVERAGE'] |
| F5 | 600 | 25 | 29 | 21 | 1150 | 428 | [] |
| F6 | 600 | 32 | 0 | 64 | 1136 | 820 | ['ONLY_ONE_OR_ZERO_TARGET_CLASSES'] |
| F7 | 600 | 120 | 190 | 50 | 960 | 2300 | [] |
| F8 | 600 | 10 | 9 | 11 | 1180 | 112 | ['MISSING_RETAINED_N_COVERAGE'] |
| F9 | 600 | 42 | 59 | 25 | 1116 | 768 | [] |
| F10 | 600 | 30 | 13 | 47 | 1140 | 420 | ['MISSING_RETAINED_N_COVERAGE'] |

### VALIDATION by family

| Family | Events | Retained | Positive | Negative | Invalid | Rows | Flags |
| --- | --- | --- | --- | --- | --- | --- | --- |
| F1 | 150 | 29 | 50 | 8 | 242 | 524 | [] |
| F2 | 150 | 14 | 15 | 13 | 272 | 284 | [] |
| F3 | 150 | 0 | 0 | 0 | 300 | 0 | ['ZERO_RETAINED_PAIRS', 'ONLY_ONE_OR_ZERO_TARGET_CLASSES', 'MISSING_RETAINED_N_COVERAGE'] |
| F4 | 150 | 0 | 0 | 0 | 300 | 0 | ['ZERO_RETAINED_PAIRS', 'ONLY_ONE_OR_ZERO_TARGET_CLASSES', 'MISSING_RETAINED_N_COVERAGE'] |
| F5 | 150 | 7 | 7 | 7 | 286 | 116 | [] |
| F6 | 150 | 7 | 0 | 14 | 286 | 188 | ['ONLY_ONE_OR_ZERO_TARGET_CLASSES', 'MISSING_RETAINED_N_COVERAGE'] |
| F7 | 150 | 31 | 48 | 14 | 238 | 572 | [] |
| F8 | 150 | 4 | 3 | 5 | 292 | 48 | ['VERY_SMALL_RETAINED_EVENT_COUNT_1_TO_4', 'MISSING_RETAINED_N_COVERAGE'] |
| F9 | 150 | 15 | 20 | 10 | 270 | 348 | [] |
| F10 | 150 | 13 | 11 | 15 | 274 | 214 | ['MISSING_RETAINED_N_COVERAGE'] |

### TRAIN by N

| N | Events | Retained | Positive | Negative | Invalid | Rows |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 1200 | 90 | 130 | 50 | 2220 | 900 |
| 6 | 1200 | 94 | 128 | 60 | 2212 | 1128 |
| 8 | 1200 | 87 | 120 | 54 | 2226 | 1392 |
| 12 | 1200 | 73 | 92 | 54 | 2254 | 1752 |
| 16 | 1200 | 99 | 62 | 136 | 2202 | 3168 |

### VALIDATION by N

| N | Events | Retained | Positive | Negative | Invalid | Rows |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 300 | 23 | 34 | 12 | 554 | 230 |
| 6 | 300 | 22 | 34 | 10 | 556 | 264 |
| 8 | 300 | 24 | 33 | 15 | 552 | 384 |
| 12 | 300 | 27 | 31 | 23 | 546 | 648 |
| 16 | 300 | 24 | 22 | 26 | 552 | 768 |

### Candidate topology

TRAIN:

| Topology | Positive | Negative | Invalid |
| --- | --- | --- | --- |
| COMPACT | 237 | 206 | 5557 |
| LINE | 295 | 148 | 5557 |

VALIDATION:

| Topology | Positive | Negative | Invalid |
| --- | --- | --- | --- |
| COMPACT | 64 | 56 | 1380 |
| LINE | 90 | 30 | 1380 |

Every retained event contains both COMPACT and LINE candidate rows.

## Statistical unit

- TRAIN: 8,340 robot-local rows from 443 independent retained source events.
- VALIDATION: 2,294 robot-local rows from 120 independent retained source events.
- Rows are clustered by split, layout, source episode, and decision event. Robot-local rows are not reported as statistically independent episodes.

## Invalid reasons

TRAIN event reasons: `{"SOURCE_TERMINATED_BEFORE_EVENT:COLLISION": 3517, "SOURCE_TERMINATED_BEFORE_EVENT:GOAL_COMPLETE": 1920, "SOURCE_TERMINATED_BEFORE_EVENT:INITIALIZATION_INVALID": 120}`.

VALIDATION event reasons: `{"SOURCE_TERMINATED_BEFORE_EVENT:COLLISION": 796, "SOURCE_TERMINATED_BEFORE_EVENT:GOAL_COMPLETE": 554, "SOURCE_TERMINATED_BEFORE_EVENT:INITIALIZATION_INVALID": 30}`.

Infrastructure conditions classified as scientific invalid: **NO**. Timeout, worker crash, writer failure, and scheduler failure misclassification counts are all zero.

## Class balance

- Aggregate TRAIN: positive=532, negative=354, invalid=11114.
- Aggregate VALIDATION: positive=154, negative=86, invalid=2760.
- Robot-local TRAIN: positive=4474, negative=3866.
- Robot-local VALIDATION: positive=1362, negative=932.
- Family, N, topology, and split distributions are canonical artifact `1b924752088e94727137e26d9d0d46e4d4475fee6675023b661dc0d71898e59e`.
- Class weighting remains `NOT_SELECTED`.

## Split isolation

- Source episode ID overlap: 0
- Decision event ID overlap: 0
- Scientific row ID overlap: 0
- Prohibited layout identity overlap: 0
- Intentionally shared structural templates: 300

## Combined root and integrity

- Combined root: `7e583ef98184767edfb95387ecc23d2ab266e2137db28a9fbb3badccaa495672`
- Combined root seal: `4fd9dda517eb5deed890ed5ac8ab5cc64841ab6c0a0a7a4047dd7b569cfb1f17`
- Independent combined-root validation: `2512735b75c47194e0b4127c67703885920430cfa5d648128bf0e9e71413f3c0`
- Physical TRAIN/VALIDATION files merged: NO
- Unresolved tasks, duplicates, partial publications, schema/hash failures, seed mismatches, and seal violations: all zero
- Postrun complete suite: 3149 passed, 0 failed, 0 publication-required xfailed

## Downstream and sealed domains

- Residual V2 started: NO
- Training operations: 0
- Hyperparameter trials: 0
- Model checkpoints: 0
- Optimizer states: 0
- Study A N24 accesses: 0
- Study B accesses: 0
- Final-test accesses: 0

Phase 9G-A1V stops here. No class weighting was selected, Residual V2 was not started, and no training occurred.
