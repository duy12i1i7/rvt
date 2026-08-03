# Phase 9B Generation Protocol Report

## Result

The narrow generation-budget addendum resolves every ambiguity recorded at the
blocked Phase 9 commit `b7edc024eeb3d76f0827f23f3fc9a0aa34a461ae`.
The original Phase 8 protocol, blocked audit and all mechanical files remain
bitwise unchanged.

Artifacts:

- `generation_budget_v1.json`, schema `rvt-generation-budget/v1`, hash
  `3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e`;
- `dataset_generation_protocol_v1.json`, schema
  `rvt-dataset-generation-protocol/v1`, hash
  `d928a7f614434b4d99395c5b75398b6277ec407cbf206e332a621f553022be57`.

Future datasets must reference the original Phase 8 protocol hash and the new
generation-budget hash. The composite manifest carries both, every split/scope
commitment, exact totals, seed/timestamp rules, retry/timeout/invalid policies
and N=24 access controls.

## Acceptance Gates

| gate | result |
|---|---|
| B1 unique budget | pass: all five dataset totals derive exactly |
| B2 no post-hoc balancing | pass: family, N, source, event and dense quotas frozen |
| B3 study separation | pass: distinct dataset IDs and cell contracts |
| B4 N=24 isolation | pass: absent from Study A train/validation, evaluation sealed |
| B5 deterministic identity | pass: canonical IDs and SHA-256-derived 32-bit seeds |
| B6 no resampling | pass: zero semantic retries and no replacement policy |
| B7 exact timeouts | pass: four wall-clock limits plus family simulator horizon |
| B8 dense target neutrality | pass: identity-only ranking interface and tests |
| B9 final-test isolation | pass: no final-test cell/job/seed constructor path |
| B10 no data | pass: zero rows, rollouts, residual jobs and training operations |

## Counts and Scope

The exact total budget is 3,120 source episodes, 15,300 decision events, 42,840
candidate-replica rollouts, 332,900 recoverability robot-candidate records and
536,000 dense residual-action records. These are frozen future budgets; Phase 9B
executed none of them.

Study B train globally allocates 200 episodes to each of S0-S5. Study B
validation deterministically rotates one five-slot source episode per cell. All
other event and source allocations follow the exact contract documents.

Phase 9B generated two protocol JSON documents only. Scientific dataset records,
rollout jobs, residual-expert jobs, model forwards/backwards, checkpoints,
optimizer states, class balancing and DAgger runs are all zero. Final-test
geometry loads and successful runtime accesses remain zero.

## Verification

The addendum adds 39 contract tests to the 1,962-test blocked Phase 9 baseline.
Phase 8 preflight, split/final-test guards, exact-budget derivation, source
allocation, timestamps, seed identity, retry, invalid-record, dense-selection
and N=24 sealing are included.

## Verdict

**C. The generation budget is complete and frozen; resume Phase 9 generation
from the existing Phase 9 plan.**
