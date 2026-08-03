# Phase 9 Generation Run Report

## Result

The Phase 9B budget and deterministic job planning are valid, but the mandatory
canonical execution canary fails before simulator step 0. Full source,
counterfactual and residual generation was therefore aborted as required.

The blocked report at `docs/PHASE9_DATASET_REPORT.md` remains bitwise preserved
from commit `b7edc024eeb3d76f0827f23f3fc9a0aa34a461ae`. This successor report records
the resumed Phase 9C execution result without overwriting that approved audit.

## Provenance

- Phase 8 protocol: `0bb68dd56ef0837f83c44dcf5281498f8c0ea934b00bbb9b3d3f298264d32147`
- Phase 9B budget: `3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e`
- composite protocol: `d928a7f614434b4d99395c5b75398b6277ec407cbf206e332a621f553022be57`
- job manifest: `801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3`
- canary audit: `f6ee1a7b652c4144f31e75574cff1ab097a61133b99aac7dc694f81c746faa2b`

## Counts

| item | planned | actual valid/emitted |
|---|---:|---:|
| source episodes | 3,120 | 0 |
| event slots | 15,300 | 0 available, 15,300 not evaluated |
| candidate replicas | 42,840 | 0 |
| recoverability rows | 332,900 capacity | 0 |
| residual rows | 536,000 capacity | 0 |
| shards | not a capacity | 0 |

There is one unique infrastructure-failed source job, two identical attempts,
zero semantic task failures and zero simulator steps. Study A N=24 generation
is incomplete and access count is 0. Study B includes N=24 in planning but has
no valid records. Final-test job/access count is 0.

## Gates

Manifest integrity, no replacement sampling, planning split integrity,
final-test isolation, Study A N=24 isolation and no-training pass. Rollout
validity and training readiness fail. Label non-vacuity, input leakage,
residual locality and residual quality are not evaluated. Reproducibility passes
only for planning and the deterministic fatal canary.

## Phase 10 Blocker

The repository lacks an approved executable binding from Phase 8 scenario
descriptors and S0-S5 sources to the frozen COMPACT/LINE controller and
transition runtime. Adding that binding requires an explicit scientific
execution contract before dataset generation can resume.

## Verdict

**D. Dataset generation, provenance, split isolation or audit is invalid.**

