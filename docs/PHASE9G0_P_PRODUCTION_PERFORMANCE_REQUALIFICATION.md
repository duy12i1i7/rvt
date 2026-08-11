# Phase 9G0-P Production Performance Requalification

## Identity

- 9G0-R evidence commit: `1676427c92d111c0aa7aebb2fe9e2cc035297605`
- 9G0-P evidence commit: `2787c32abdf2c3265ffd7442e1f3684ba7dc1794`
- Scientific source commit: `8cf64481cd17b2c44f7007d3722a8110e53cae46`
- Operational execution commit: `6818d8aa07aeb55a43dc42741499d9a24d540332`
- Production image: `sha256:88ecf1aac7cd95b5ba50811950090c13f78362274e5c5cdaeafaafde29a115f4`
- Readiness root: `32a061e5f5c2566613765dfbe78ee81328c9f931942622abf7299e7f56baeb15`

All RB19, RB20, RB21P, RB21-TARGET, 9G0 startup-stop, 9G0-R,
generation-provenance V2, Readiness V4, official-generator and Command Plan V2
roots were revalidated without stale/current ambiguity.

## Recoverability

- W=1: n=24, wall 77.65 s, median 1.47 s, p90 8.12 s, p95 8.63 s,
  max 8.74 s, peak RSS 293.7 MB.
- Predeclared workers: 1, 6, 12, 18, 22.
- Selected: `PROFILE_RECOVERABILITY_V1`, W=12, numeric threads=1,
  chunk=1, infrastructure timeout=60 s.
- W=12 wall: 10.14 s; speedup
  7.65x; efficiency
  0.638.
- Chunk wall times c1/c2/c4: 10.31 / 18.75 / 32.86 s. Chunk=1 also has
  the smallest retry blast radius and best resume granularity.
- Semantic digest is identical at every W and chunk:
  `c1690c89f737678de83fe36041f6433d909aa36415b7442146bc5c8afa3ed033`.
- Full authorized capacity: 15,000 events, 30,000 candidate aggregates,
  42,000 replica executions, 318,500 robot-candidate row capacity.
- Projection: 3.58 wall-hours,
  31.68 CPU-hours, 10.34 GB staging.

## Residual V2

- W=1: n=25, wall 693.98 s, median 10.23 s, p90 70.67 s,
  p95 110.33 s, max 134.49 s, peak RSS 215.2 MB.
- Predeclared workers: 1, 4, 8, 12, 18, 22.
- Selected: `PROFILE_RESIDUAL_V2_V1`, W=8, numeric threads=1,
  chunk=1, infrastructure timeout=360 s.
- W=8 retains 99.39% of maximum measured
  throughput with lower RSS and p95 than W>=12.
- Chunk wall times c1/c2/c3: 190.51 / 202.78 / 222.11 s.
- Semantic digest is identical at every W and chunk:
  `7e8c9136e280025ba219716162c879f9d84d8b3998cf366de59ac5b7e11b97db`.
- K=16 strict upper bound: 520,960 states;
  candidate evaluations: 4,688,640.
- Projection: 501.6 to
  1102.8 wall-hours,
  4004.4 CPU-hours,
  21.58 GB staging.

## Failure And Resume

Eight scoped target injections passed: worker death before completion, worker
death after compute/before durable ACK, termination between chunks, duplicate
submission, partial Recoverability row-set/audit, partial Residual row, writer
failure, and exact nine-candidate replay. Candidate-pair and Residual partial
scientific publications were both zero. Duplicate canonical records are no-ops.

Timeouts are infrastructure-only. They cannot become `VALID_TASK_NEGATIVE`,
`GENERATION_INVALID`, or `NO_ELIGIBLE_ACTION`.

## GPU And H4

The RTX 5000 Ada is container-visible, but the qualified generation PyTorch is
CPU-only. Simulator, controller, safety, transition protocol, Target V4,
Recoverability counterfactuals, Residual Expert V2 and ego-graph construction
remain CPU-authoritative. Generation GPU utilization is none.

H4 is `H4_OPERATIONAL_RISK_BUT_FEASIBLE`: the Residual path is multi-week and
heavy-tailed, but RAM, storage, timeout, idempotency and resume are qualified
without changing K=16, nine candidates or horizon.

## Study Sequence

Required order is Study A train/validation generation, Study A model selection
and checkpoint freeze, then Study A N24 zero-shot evaluation and immutable
recording. Study B remains held until that sequence is complete. Study A N24
and final test remain `SEALED_NOT_AUTHORIZED`.

## Contract And Commands

- Operational contract: `1a4e0fcbe49b94c3375125d0ef8421e7129b801491cec309e49ce4bc24adcc12`.
- Command Plan V2 operational addendum: `0bde430d679729faa22e06b50c45523166c7fbc55143d41d147da9f4acd6980f`.
- Eight commands resolve; all have authorization=false; none was executed.
- Operational preflight: 22 negative cases, zero escapes.

## Tests And Isolation

- Local complete suite: 3,048 passed, 0 failed, 0 publication-required xfailed.
- Target clean detached suite at `2787c32abdf2c3265ffd7442e1f3684ba7dc1794`: 3,048 passed, 0 failed,
  0 publication-required xfailed.
- A read-only mount attempt produced 27 EROFS harness failures and was discarded;
  the writable detached rerun closed all 27 without source changes.
- Official run IDs, STAGING writes, scientific rows, shards, training,
  checkpoints, optimizer states, Study A N24 accesses and final-test accesses:
  all zero.

## Verdict

**C. Actual official production producers are operationally qualified.**

Recoverability is ready for explicit scoped owner authorization. Residual V2 is
also ready for explicit scoped owner authorization, with its measured
multi-week H4 operational risk disclosed. Authorization remains false in this
phase.
