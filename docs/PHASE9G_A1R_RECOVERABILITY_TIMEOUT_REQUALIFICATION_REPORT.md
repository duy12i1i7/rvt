# Phase 9G-A1R Recoverability Timeout Requalification Report

## Scope and outcome

Phase 9G-A1R requalified only Recoverability production timeout and exact-resume
operations. It did not change the simulator, controller, Target V4, selector,
counterfactual generation, row builder, scenarios, randomness, or other frozen
science. Residual V2 was not started and training operations remained zero.

The 60-second timeout was a false operational limit on a legitimate scientific
long tail. It was replaced by a derived 243-second infrastructure watchdog.
The official continuation then passed the old timeout boundary and committed 83
additional complete event transactions. It subsequently stopped on a separate,
deterministic exception in the frozen S3 source policy. Repairing that exception
would require a frozen-science change, which is outside this phase.

## Root cause

### Original timeout

- Classification: `LEGITIMATE_LONG_TAIL`.
- Both timeout observations were the same atomic unit, not different units at a
  common boundary.
- Study/split: `study_a_zero_shot/train`.
- Family/layout/N: `F2`,
  `b0883e9e58df9dbae2deb41dfa9d7455e985ac80794fd89bac035ad0a1bef847`,
  `N=12`.
- Source/event: `S0_SCRIPTED_DIAGNOSTIC`, episode 1, event 2, step 400,
  60.0 seconds.
- Candidate/replica/seed: COMPACT (5), replica 0, matched disturbance seed
  `3531133071`.
- Atomic identity:
  `5d4f5bbe58cb8ae44b664da9cba4a50e4a462cab8bb05b638982486785b7bc1d`.

The source reached `GOAL_COMPLETE` at step 383 before the planned event. The
unit terminated normally when allowed to run. There was no deadlock, resource
starvation, writer stall, or scheduler cancellation.

### Continuation blocker

The official continuation stopped at the first unresolved source unit that
raised `ValueError: S3 measured width must be finite and nonnegative`:

- Family/layout/N: `F3`,
  `59dd0a284ff8482c2831245429ba843d4439d9ec6f8735696ae84e651d714dd1`,
  `N=12`.
- Source/event: `S3_FROZEN_LOCAL_GEOMETRIC_SELECTOR`, episode 0, event 0,
  step 90, 13.5 seconds.
- Official candidate/seed: COMPACT (5), matched disturbance seed `1313388664`.
- Atomic identity:
  `7d7f2859e7f863031676d5c972dca4e03a4a5dd84ba438cdc7753bb26896b65b`.

Two COMPACT diagnostic replays and one LINE replay reproduced the exception in
approximately 0.092 seconds with the same measured width,
`-0.6143634774571596 m`. The source failure is deterministic and candidate
independent. It created no candidate result, scientific disposition, row,
candidate-pair transaction, partial transaction, or official STAGING write.
It must not be converted to `GENERATION_INVALID` without a separately approved
scientific decision.

## Invalid audit

The initial 216 `GENERATION_INVALID` aggregates were all authoritative frozen
source terminations:

| Reason | Aggregates |
|---|---:|
| `SOURCE_TERMINATED_BEFORE_EVENT:COLLISION` | 70 |
| `SOURCE_TERMINATED_BEFORE_EVENT:GOAL_COMPLETE` | 146 |
| Infrastructure-derived invalids | 0 |

No 60-second timeout, worker crash, writer failure, retry exhaustion, scheduler
cancellation, process termination, or missing result was classified as a
scientific invalid. Required continuation answer: **NO infrastructure
misclassification**.

At the later durable boundary, the descriptive invalid count was 380: 220
collision terminations and 160 goal-complete terminations. The unresolved S3
exception is excluded from these counts.

## Diagnostic replay

- Isolated W=1 runtimes: 87.864 and 87.216 seconds.
- Production-equivalent W=12 runtime for the exact candidate unit: 91.669
  seconds.
- Termination: normal frozen-source `GOAL_COMPLETE`, yielding the same
  `GENERATION_INVALID` semantic result.
- Repeated W=1 and W=12 scientific semantic digests matched exactly.
- Peak isolated RSS: 600,600,576 bytes; W=12 worker RSS for the exact unit:
  281,534,464 bytes.

## Long-tail set

The set was predeclared from authorized Study-A train/validation nonsealed
content and contained 9 events, 18 candidate aggregates. It included the timed
class, same-family/N cases, long horizons, three-replica cases, changed
topologies, and prior slow structures. Study A N24, Study B, and final test were
excluded.

| W=12 candidate latency | Seconds |
|---|---:|
| n | 18 |
| median | 10.081 |
| p90 | 49.388 |
| p95 | 91.409 |
| max | 91.669 |
| per-replica max | 5.761 |

Maximum candidate-pair reconciliation time was 0.035 seconds and maximum
writer time was 0.031 seconds. W=1 and W=12 produced the same scientific
semantic digest. W=12 did not cause pathological tail behavior, so no worker
matrix or worker-count change was justified.

## Profiles and timeout proof

| Field | Old profile | Qualified profile |
|---|---:|---:|
| workers | 12 | 12 |
| numeric threads per worker | 1 | 1 |
| chunk (atomic units) | 1 | 1 |
| infrastructure timeout | 60 s | 243 s |

The predeclared derivation was:

```text
measured envelope = 109.122903788 s
team-size scaling = (N_max / N_observed)^2 = (16 / 12)^2
operational safety margin = 1.25
timeout = ceil(109.122903788 * (16 / 12)^2 * 1.25) = 243 s
```

It uses the measured max/envelope, maximum frozen structure and a declared
safety margin, not the mean or the Residual timeout.

A forced 5-second diagnostic timeout exited as infrastructure failure and
created zero result artifacts, accepted dispositions, candidate aggregates,
rows, pair transactions, or partial commits. The same candidate pair completed
under 243 seconds in 175.359 seconds with the reference scientific semantic
digest. Thus timeout remains infrastructure-only.

## Contract and authorization

- Historical operational contract:
  `1a4e0fcbe49b94c3375125d0ef8421e7129b801491cec309e49ce4bc24adcc12`.
- Recoverability-only amendment:
  `1821badc6b09c2417a3fff98bb2f97673a69cdeff002b9ac1a64fac927d806e8`.
- Parent owner authorization:
  `cc42e48fd7b557a53bb2e8f385e0dda776c4c0a9c8ec719c040476d5d9c06a99`.
- Narrow authorization continuation:
  `fc83e2ff0671edba662852d68515bd28cba31cfb214e728afaa857a0f7164e9a`.
- Successor continuation identity:
  `98be39bf8653ea683aa6a948bb9419deb5c64b67c1e15a5b7215807a5b43f129`.

The parent run immutably bound the old operational contract, so a successor run
identity was required. It references the parent and the same STAGING namespace;
it is not an independent dataset. The authorization scope remains only Study-A
train/validation Recoverability, with train before validation.

## STAGING integrity

- Initial rows: 318.
- Canonical checkpoint:
  `9012344ea59b0e415809ff76753b7374e60533c6320dd94dee1f0c43e2a5d5ab`.
- Checkpoint preimage:
  `b1fc6c7ddc238c5cbb961f191ad6e48c6e05f0d985d80548d4ee4ac2fa1d2f5e`.
- Initial rows reused: 318; existing rows re-emitted: 0.
- New rows committed before the S3 stop: 24.
- Current rows: 342; duplicate identities: 0; partial publications: 0.
- Current storage: 6,576,210 bytes.

All 127 parent transactions and all 83 new transactions are complete. STAGING
was returned to read-only immediately after the hard stop. The failed atomic
unit remains scientifically unresolved. The final target guard passed with zero
Phase 9G-A1R containers, directory mode `555`, 210 complete transaction files,
zero partial files, and no validation STAGING namespace.

## Official Recoverability status

Recoverability is incomplete, so no final dataset manifest or dataset-manifest
hash exists.

| Metric | Train | Validation | Authorized total |
|---|---:|---:|---:|
| events | 210 / 6000 | 0 / 1500 | 210 / 7500 |
| candidate aggregates | 420 / 12000 | 0 / 3000 | 420 / 15000 |
| labelable candidate replicas completed | 52 | 0 | 52 |
| positive aggregates | 30 | 0 | 30 |
| valid negative aggregates | 10 | 0 | 10 |
| generation-invalid aggregates | 380 | 0 | 380 |
| pair-retained events | 20 | 0 | 20 |
| pair-dropped events | 190 | 0 | 190 |
| scientific rows | 342 | 0 | 342 |

Partial train breakdown at the durable stop:

| Family | N | Candidate | Positive | Negative | Invalid |
|---|---:|---|---:|---:|---:|
| F1 | 8 | LINE | 11 | 1 | 48 |
| F1 | 8 | COMPACT | 11 | 1 | 48 |
| F2 | 12 | LINE | 4 | 1 | 55 |
| F2 | 12 | COMPACT | 1 | 4 | 55 |
| F3 | 12 | LINE | 0 | 0 | 30 |
| F3 | 12 | COMPACT | 0 | 0 | 30 |
| F8 | 5 | LINE | 3 | 0 | 57 |
| F8 | 5 | COMPACT | 0 | 3 | 57 |

The continuation itself had zero timeouts, zero infrastructure retries and zero
scientific retries. Across the lineage there are two historical timeouts, one
historical run-level resume and this one successor continuation. One confirmed
frozen-source worker failure remains unresolved. Observed wall time is 490.208
seconds across the stopped parent and continuation; sampled CPU is 1.02146
CPU-hours. During continuation the 83-event telemetry recorded 0.225812
CPU-hours, 6.981 average active CPU cores, peak per-worker RSS 294,920,192
bytes, and maximum combined reconciliation/durable-writer overhead 0.1375
seconds. Separate writer latency was not emitted by this official telemetry, so
that quantity is not retrospectively invented.

## Sealed domains and downstream

| Operation/domain | Count or status |
|---|---:|
| Study A N24 accesses | 0 |
| Study B accesses | 0 |
| final-test accesses | 0 |
| Residual V2 operations | 0, not started |
| training operations | 0 |

## Verification and evidence

- Focused timeout, transaction, resume, authorization and preflight tests passed.
- Complete suite: 3085 passed, 0 failed, 0 publication-required xfailed.
- Continuation stop audit:
  `90aa05f702479051f3f021e4668432c712a067c8e5d127cd6cce96d179ed0a28`.
- Frozen-source diagnostic summary:
  `e1efaf9feb39b35155e2b575b5bc1e2e50e91fd9cf6ad6b32c79583e0b29d1e1`.

## Verdict

**A. Recoverability continuation requires changing frozen science.**

The timeout/resume repair itself is scientifically invariant and operationally
qualified. Verdict C is unavailable because Recoverability train/validation did
not complete. Verdict B is not selected because the existing official data is
consistent and the operational repair did not change scientific semantics. No
science repair is attempted in Phase 9G-A1R.
