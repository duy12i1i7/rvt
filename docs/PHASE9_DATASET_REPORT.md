# Phase 9 Dataset Report

## Executive Result

Phase 9 stopped at the mandatory Phase 9C budget-completeness gate. Phase 9A
preflight passes and Phase 9B study separation is unambiguous, but the approved
Phase 8 contracts do not determine one unique full generation plan. Generating
jobs would require new episode, seed/timestamp allocation, Study A N=24, Study B,
dense-sample and retry choices after protocol approval.

No simulator rollout, dataset row, shard, model forward, backward pass,
checkpoint selection, training, DAgger or final-test access was performed.

## What Is Frozen

The approved Study A upper bounds are:

| split | decision events | candidate-replica rollouts | local recoverability rows | dense rows |
|---|---:|---:|---:|---:|
| train | 6,000 | 16,800 | 112,800 | 250,000 |
| validation | 1,500 | 4,200 | 28,200 | 50,000 |

The rollout totals account for one replica in F1-F7/F10 and three matched
replicas in F8/F9. The local-row totals account for both candidates and every
robot in `N={5,6,8,12,16}`. These are upper bounds, not authorization to fill the
caps using an invented episode plan.

Other frozen limits are 120 train and 30 validation events per family/team-size
cell, at most 12 events per episode, at least 1.5 s between decision events, at
most 64 retained residual timesteps per episode and at least 0.45 s between
residual samples.

## Blocking Incompleteness

The approved Phase 8 tree does not declare:

1. Study A episode counts by split/family/team-size;
2. the deterministic mapping from event index to episode, layout, seeds and timestamp;
3. the Study A N=24 evaluation budget;
4. the Study B train/validation generation budget;
5. exact dense-action cell counts and episode allocation beneath the caps;
6. maximum generation retries;
7. a wall-clock generation-job timeout policy;
8. initialization-rejection denominator and replacement treatment.

The five trajectory sources are fixed at 20% each, and sampling is declared as
70% event-balanced plus 30% trajectory-uniform, but those rates do not resolve
the missing episode/layout/seed/timestamp mapping.

## Phase 9C Stop Rule

The request states: if approved Phase 8 documents do not determine a generation
budget uniquely, stop with explicit protocol incompleteness. It also forbids
inventing or silently enlarging episodes, per-team budgets, retries and sample
counts. The implemented gate therefore raises
`ProtocolIncompletenessError` before deterministic job planning.

Machine-readable evidence:

- `results/rvt_fd24/datasets/phase9_preflight_audit.json`;
- `results/rvt_fd24/datasets/phase9_generation_budget.json`.

The job manifest, dataset manifests, label/residual audits, shards, strict data
loaders and dry backward are intentionally absent because they are downstream of
the failed Phase 9C gate. Creating empty or synthetic substitutes would not
satisfy the scientific contracts.

## Gates and Counts

| item | result |
|---|---|
| Phase 9A provenance preflight | pass, 24/24 checks |
| Phase 9C unique budget | fail |
| generation jobs | 0 |
| completed / failed / invalid jobs | 0 / 0 / 0 |
| recoverability records | 0 |
| residual-action records | 0 |
| dataset shards | 0 |
| trained checkpoints | 0 |
| optimizer states retained | 0 |
| class weighting or resampling | none |
| DAgger rounds | 0 |
| final-test geometry loads | 0 |
| final-test runtime accesses | 0 |

P9-G1 through P9-G13 are not evaluated as dataset gates because no valid dataset
was authorized. This is not evidence against recoverability or residual target
semantics; it is a protocol completeness failure before data generation.

## Required Repair Before Phase 9 Resume

An explicit protocol amendment must freeze the eight missing declarations above
without using observed label distributions. It must receive a new protocol hash;
the approved Phase 8 manifest cannot be silently reinterpreted. After that
review, Phase 9 should restart from deterministic job planning on a new approved
source commit while preserving this negative audit.

## Verdict

**D. Dataset generation, provenance, split isolation or audit is invalid.**

Here the confirmed defect is generation-protocol incompleteness; provenance and
split preflight themselves pass.
