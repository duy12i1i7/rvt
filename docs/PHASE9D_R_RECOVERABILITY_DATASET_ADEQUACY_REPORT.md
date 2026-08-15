# Phase 9D-R Recoverability Dataset Adequacy Report

## Identity

- Input closure commit: `6ce4a37f195875e6568e2bbed2d1e2dfea103946`
- Audit source commit: `d24f6b43aaf841534d9993e9286d05dbab1c9fc3`
- Branch: `research/rvt-phase9d-r-recoverability-data-audit-v1`
- TRAIN manifest: `4ac3d2cb65a8b5d656a5d982b344466868f8deaa8cef2b93af7ce824e9387caf`
- VALIDATION manifest: `c991aa3016b38b524a14d9b7037b63d97c2cbbb7d92279fc5a297b9c55d4989e`
- Combined dataset root: `7e583ef98184767edfb95387ecc23d2ab266e2137db28a9fbb3badccaa495672`
- Read-only input audit: `c305b868bcbf1369b7c6f5ad924dd8261f0c8c3d99c12a399bc4ce0ac5e2341b`

## Coverage Status

`COVERAGE_STRUCTURALLY_MISSING` is assigned when any A1V family record has an
authoritative descriptive flag: zero retained pairs, one through four retained
pairs, only one or zero target classes, or at least one authorized N with zero
retained events. It does not mean any family/N/topology cell was unscheduled.

- Authoritative missing family cells: 11
- Contributing zero-retained family x N cells: 28
- Explicit family cells: `TRAIN:F2[MISSING_RETAINED_N_COVERAGE]; TRAIN:F3[ONLY_ONE_OR_ZERO_TARGET_CLASSES,MISSING_RETAINED_N_COVERAGE]; TRAIN:F4[ZERO_RETAINED_PAIRS,ONLY_ONE_OR_ZERO_TARGET_CLASSES,MISSING_RETAINED_N_COVERAGE]; TRAIN:F6[ONLY_ONE_OR_ZERO_TARGET_CLASSES]; TRAIN:F8[MISSING_RETAINED_N_COVERAGE]; TRAIN:F10[MISSING_RETAINED_N_COVERAGE]; VALIDATION:F3[ZERO_RETAINED_PAIRS,ONLY_ONE_OR_ZERO_TARGET_CLASSES,MISSING_RETAINED_N_COVERAGE]; VALIDATION:F4[ZERO_RETAINED_PAIRS,ONLY_ONE_OR_ZERO_TARGET_CLASSES,MISSING_RETAINED_N_COVERAGE]; VALIDATION:F6[ONLY_ONE_OR_ZERO_TARGET_CLASSES,MISSING_RETAINED_N_COVERAGE]; VALIDATION:F8[VERY_SMALL_RETAINED_EVENT_COUNT_1_TO_4,MISSING_RETAINED_N_COVERAGE]; VALIDATION:F10[MISSING_RETAINED_N_COVERAGE]`
- Unexpected executable/manifest gaps: 0
- Cause classification: `EXPECTED_FROM_FROZEN_SCIENCE` for every missing cell

## TRAIN by Family

| Family | Scheduled events | Retained | Positive | Negative | Invalid | Rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| F1 | 600 | 137 | 191 | 83 | 926 | 2776 |
| F2 | 600 | 40 | 41 | 39 | 1120 | 628 |
| F3 | 600 | 7 | 0 | 14 | 1186 | 88 |
| F4 | 600 | 0 | 0 | 0 | 1200 | 0 |
| F5 | 600 | 25 | 29 | 21 | 1150 | 428 |
| F6 | 600 | 32 | 0 | 64 | 1136 | 820 |
| F7 | 600 | 120 | 190 | 50 | 960 | 2300 |
| F8 | 600 | 10 | 9 | 11 | 1180 | 112 |
| F9 | 600 | 42 | 59 | 25 | 1116 | 768 |
| F10 | 600 | 30 | 13 | 47 | 1140 | 420 |

## VALIDATION by Family

| Family | Scheduled events | Retained | Positive | Negative | Invalid | Rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| F1 | 150 | 29 | 50 | 8 | 242 | 524 |
| F2 | 150 | 14 | 15 | 13 | 272 | 284 |
| F3 | 150 | 0 | 0 | 0 | 300 | 0 |
| F4 | 150 | 0 | 0 | 0 | 300 | 0 |
| F5 | 150 | 7 | 7 | 7 | 286 | 116 |
| F6 | 150 | 7 | 0 | 14 | 286 | 188 |
| F7 | 150 | 31 | 48 | 14 | 238 | 572 |
| F8 | 150 | 4 | 3 | 5 | 292 | 48 |
| F9 | 150 | 15 | 20 | 10 | 270 | 348 |
| F10 | 150 | 13 | 11 | 15 | 274 | 214 |

## TRAIN by N

| Team Size | Scheduled events | Retained | Positive | Negative | Invalid | Rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 1200 | 90 | 130 | 50 | 2220 | 900 |
| 6 | 1200 | 94 | 128 | 60 | 2212 | 1128 |
| 8 | 1200 | 87 | 120 | 54 | 2226 | 1392 |
| 12 | 1200 | 73 | 92 | 54 | 2254 | 1752 |
| 16 | 1200 | 99 | 62 | 136 | 2202 | 3168 |

## VALIDATION by N

| Team Size | Scheduled events | Retained | Positive | Negative | Invalid | Rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 300 | 23 | 34 | 12 | 554 | 230 |
| 6 | 300 | 22 | 34 | 10 | 556 | 264 |
| 8 | 300 | 24 | 33 | 15 | 552 | 384 |
| 12 | 300 | 27 | 31 | 23 | 546 | 648 |
| 16 | 300 | 24 | 22 | 26 | 552 | 768 |

## H1

Frozen statement: "Recoverability selection improves episode task success by at least 0.08 absolute over both direct classification and local geometric selection, while meeting the frozen collision gate."

- Primary metric/unit: episode task success on paired episodes.
- Required nonsealed Study-A N: `[5, 6, 8, 12, 16]`.
- Candidates: COMPACT and LINE.
- Baselines: local geometric selector, direct classifier, strongest fixed deployable baseline.
- Pooled primary comparisons are predeclared; per-family effect claims are not.
- A minimum label-support rule was predeclared. Gate 4 requires at least 30 retained VALIDATION events per primary family.
- Gate 4 result: FAIL in F1, F2, F3, F4, F5, F6, F8, F9 and F10; only F7 reaches 30.
- H1 comparison classification: `NOT_IDENTIFIABLE_FROM_CURRENT_DATA` under the frozen gate.
- Missing coverage affects primary H1 support and secondary diagnostics.

No post-hoc minimum count or percentage was introduced.

## Invalid Reasons

- TRAIN source events: collision=3517, goal-complete=1920, initialization-invalid=120.
- VALIDATION source events: collision=796, goal-complete=554, initialization-invalid=30.
- GENERATION_INVALID candidate aggregates: TRAIN=11,114; VALIDATION=2,760.
- Transition/Target-V4/S3 generation-invalid events: 0/0/0.
- Infrastructure conditions misclassified as scientific invalid: NO.
- Only positive and valid-negative rows enter supervised BCE; GENERATION_INVALID is never mapped to label 0.

## Statistical Unit

- TRAIN: 443 retained source events and 8,340 robot-local rows.
- VALIDATION: 120 retained source events and 2,294 robot-local rows.
- Clustering keys: split, layout, source episode and decision event.
- Robot rows are not independent observations.
- A retained event emits `2*N` rows, but the frozen loss averages candidates and robots within the event, then events. Effective event weight is therefore 1 for every N; a raw row mean is prohibited.

## Class Balance

- TRAIN aggregate: positive=532, negative=354.
- VALIDATION aggregate: positive=154, negative=86.
- TRAIN rows: positive=4474, negative=3866.
- VALIDATION rows: positive=1362, negative=932.
- Decisive TRAIN events COMPACT-only/LINE-only: 70/128.
- Decisive VALIDATION events COMPACT-only/LINE-only: 20/46.

### By Candidate Topology

TRAIN:

| Candidate Topology | Scheduled events | Retained | Positive | Negative | Invalid | Rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| COMPACT | 6000 | 443 | 237 | 206 | 5557 | 4170 |
| LINE | 6000 | 443 | 295 | 148 | 5557 | 4170 |

VALIDATION:

| Candidate Topology | Scheduled events | Retained | Positive | Negative | Invalid | Rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| COMPACT | 1500 | 120 | 64 | 56 | 1380 | 1147 |
| LINE | 1500 | 120 | 90 | 30 | 1380 | 1147 |

## Class Weight

- Decision: `NONE_UNWEIGHTED_BCE`.
- The aggregate imbalance is moderate and consistent in direction across splits.
- Weighting cannot repair structural missingness; no resampling, family weighting or N weighting is introduced.

## Decisions

- Dataset adequacy: `RECOVERABILITY_DATASET_INADEQUATE_FOR_FROZEN_H1`.
- Residual: `HOLD_RESIDUAL_PENDING_RECOVERABILITY_SCIENTIFIC_DECISION`.
- Training: `RECOVERABILITY_TRAINING_BLOCKED`.
- Dataset mutation: 0.
- Residual generation/training/HP trials/checkpoints/optimizer states: 0/0/0/0/0.
- Study A N24, Study B and final-test dataset accesses: 0/0/0.

## Verdict

**C. Recoverability coverage, H1 identifiability and the class-weighting decision are closed. Residual generation is held and Recoverability training is blocked by the predeclared family-support gate.**
