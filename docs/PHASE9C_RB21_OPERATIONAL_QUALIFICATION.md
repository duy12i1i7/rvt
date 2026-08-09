# Phase 9C-RB21 Target Operational Qualification

## Verdict

**C. Authorized for the explicitly listed generation scope; scientific
semantics are frozen, reproducible, portable and operationally qualified.
Official Phase-9 generation may begin only on explicit owner instruction.**

This resumes RB21-TARGET after the approved RB21P portability requalification.
It is an operational qualification only. No scientific runtime, controller,
safety projection, Target V4 predicate, counterfactual horizon, candidate set,
replica contract, identity, utility, selector, target builder, or model contract
changed.

No official data was generated and no training ran.

## Identity

| Field | Value |
|---|---|
| Scientific source checkpoint | `a08f6f506333a20b71b60fc366c4a36d15e289ae` |
| Evidence branch | `research/rvt-rb21-target-performance-v1` |
| Evidence commit | Git commit containing this report and readiness root |
| Qualified image | `sha256:30e6dea61d67eb255e814996cf737140a3b47eac62fb74ecf303df58e280138b` |
| Qualified image source | `8bfabd48969f1fa1e13a0a268a6df1cb366e90cc` |
| RB19 root | `e8317ad3e9facc76511098503cdad55dfc065dedd8fc2b530a2b25845c3f5571` |
| RB20 reproduction | `8c55f4ef40be509dc6e0bc678467873e5ebd0ce60d0195a2227555676114b95a` |
| RB21P artifact | `0330c25a436a42422d8f8d07ae3426c930628f32bcd2a0d58ca8204874290900` |
| RB21P root | `fcc218e4bc88546240789043aa9e160d1fa39b82701637ebd6af19f2f8dcc176` |
| Target V4 | `54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee` |

The final clean-detached exact-image test result is the verification attached
to the evidence commit. The already qualified RB21P baseline was `2978 passed,
0 failed, 0 xfailed` on the same image.

## Target Environment

The qualified target is Windows host `AVIS`, Windows 11 Pro
`10.0.26200.8875`, Intel Core Ultra 9 285K, 24 logical CPUs, and
68,053,331,968 bytes host RAM. WSL 2.7.10.0 runs Ubuntu 24.04.4 LTS with kernel
6.18.33.2, 24 CPUs, 33,323,384,832 bytes RAM, and 8,589,934,592 bytes swap.

Docker Desktop 4.80.0.232116 / Engine 29.6.1 exposes Linux/amd64 and the exact
qualified image above. Production data paths are Linux-native ext4:

- staging: `/home/avis/rvt-data/staging`;
- final: `/home/avis/rvt-data/final`;
- temporary: `/home/avis/rvt-data/temp`;
- audit: `/home/avis/rvt-data/audit`.

## Benchmark Manifest

Target manifest V2 hash:
`4dca5d1dc85f6d2ceb9ce64a16f2ff89578a323c86b44965029a87b9f43af377`.

The frozen diagnostic workload contains eight train/validation cases from F1,
F5, F8, and F9 at N=5, 8, 12, and 16. It covers short and long continuation,
changed topology, communication degradation, dynamic obstacle, LABELED, and a
naturally occurring NO_ELIGIBLE_ACTION disposition.

| Atomic branch | Units | Inner executions |
|---|---:|---:|
| Recoverability | 30 | 58 frozen replica rollouts |
| Residual V2 | 30 | 270 candidate evaluations |

Median, p90, p95, and empirical maximum are reported. P99 is not reported
because 30 atomic units per branch are insufficient.

Manifest V1 contained one unreachable `rb21-f9-n16-validation` state at step
60. Exact-image reachability evidence proved that the episode terminated before
that state, no counterfactual was executed, and no successful timing artifact
was emitted. Manifest V2 removed only that nonexistent state before successful
timing; selection did not use performance results.

Study A N24 and final-test are absent from both benchmark manifests.

## Single Worker

| Measurement | Recoverability | Residual V2 |
|---|---:|---:|
| Atomic units | 30 | 30 |
| Wall time | 443.094 s | 895.701 s |
| Throughput | 0.067706 unit/s | 0.033493 decision/s |
| Median atomic latency | 5.817 s | 17.688 s |
| P90 | 46.025 s | 76.649 s |
| P95 | 68.588 s | 90.575 s |
| Maximum | 76.498 s | 99.018 s |
| Peak RSS | 218,365,952 B | 219,430,912 B |
| One-core CPU utilization | 99.75% | 99.86% |

Recoverability measured 58 individual replicas. Residual measured all 270
candidate continuations; candidate p95 was 9.967 s and maximum was 15.030 s.
Residual dispositions were 27 LABELED and 3 NO_ELIGIBLE_ACTION. Serialization
remained a small fraction of atomic runtime.

## Worker Scaling

The predeclared matrix was `W={1,2,4,6,8,12,16}`. It was derived from 24 CPUs,
33.3 GB WSL RAM, the measured W1 RSS, 25% RAM headroom, and four logical CPUs
of host headroom.

| W | Aggregate unit/s | Speedup | Efficiency | Peak aggregate RSS |
|---:|---:|---:|---:|---:|
| 1 | 0.044816 | 1.000 | 1.000 | 219,430,912 B |
| 2 | 0.087662 | 1.956 | 0.978 | 439,222,272 B |
| 4 | 0.165496 | 3.693 | 0.923 | 876,818,432 B |
| 6 | 0.199460 | 4.451 | 0.742 | 1,311,891,456 B |
| 8 | 0.258362 | 5.765 | 0.721 | 1,750,036,480 B |
| 12 | 0.280407 | 6.257 | 0.521 | 2,614,145,024 B |
| 16 | 0.290389 | 6.480 | 0.405 | 3,466,756,096 B |

Every worker count produced the same branch-specific
SCIENTIFIC_SEMANTIC_DIGEST. Full W1 and W12 scientific projections are exactly
equal. W12 is the smallest configuration with efficiency at least 0.5 and
throughput within 95% of the maximum eligible configuration. W16 adds only
about 3.6% throughput and falls below the frozen efficiency floor.

All six nested thread controls are one. Scientific CUDA execution is false.

## Chunking

Chunk sizes `C={1,2,4,8}` were frozen after worker selection and before chunk
timing. All chunks preserved the exact scientific digest.

| C | Recoverability unit/s | Residual decision/s | Retry blast radius |
|---:|---:|---:|---:|
| 1 | 0.330456 | 0.243524 | 1 atomic unit |
| 2 | 0.229690 | 0.147103 | 2 atomic units |
| 4 | 0.119131 | 0.084046 | 4 atomic units |
| 8 | 0.096566 | 0.066156 | 8 atomic units |

Chunk 1 is selected for both branches. It has the highest measured throughput,
the finest resume granularity, and the smallest failure blast radius. A
residual decision always contains all nine candidates and a recoverability unit
always contains all frozen replicas.

## Timeout

At W12/C1, recoverability p95/max were 75.202/82.290 s and residual p95/max
were 101.228/109.299 s. Across every worker/chunk run the empirical maxima were
83.565 s and 111.410 s. The maximum serialization time was 74.563 microseconds.

The authoritative control period is 0.15 s and maximum episode horizon is
180 s, or 1200 intervals. The largest observed residual and recoverability
atomic units used 4248 and 1101 aggregate intervals. Scaling the global maxima
to the theoretical 10,800 residual and 3600 recoverability interval bounds
gives 283.245 s and 273.236 s. The frozen derivation is:

`3 * max(283.245, 273.236) + 60 = 909.736 s`

Rounding upward to the next 300-second boundary selects **1200 seconds**. A
timeout is INFRASTRUCTURE_FAILURE only. The injection probe emitted no target
row, did not evaluate Target V4 from timeout, did not truncate a rollout, and
did not change a scientific horizon. The historical 1800 s value is rejected.

## Writer And Resume

At W12 the writer committed 128 canonical records at 75.382 record/s and
0.532 MB/s. This is over 268 times the selected aggregate scientific-unit rate;
all commits validated. The writer is not the throughput bottleneck.

The exact target ext4 probe covered crashes before completion, after compute
but before acknowledgement, termination between chunks, duplicate submission,
partial row, partial sidecar, failure before promotion, and insufficient
temporary space. Partial units were never complete, attempts remained visible,
duplicate identical work was idempotent, changed-science duplicates were
rejected, and resumed record/sidecar hashes were exact. Semantic retries are
zero; the infrastructure retry limit is one.

## Storage

Canonical maximum observed sizes were used, not one selected row. The full
projection is deliberately conservative: every recoverability record receives
the largest observed replica sidecar, and every residual slot reserves the
largest LABELED record, candidate sidecar, and NO_ELIGIBLE audit envelope.

| Component | Upper bytes |
|---|---:|
| Scientific payload | 3,377,407,600 |
| Audit payload | 6,533,802,400 |
| Index and manifests | 235,473,190 |
| One complete dataset | 10,146,683,190 |
| Staging + final + 2% resume + 25% temporary | 23,032,970,842 |
| Available target ext4 space | 1,024,412,712,960 |

Headroom is 44.476x against a required minimum of 2.0x.

## Capacity And H4

| Branch | Frozen upper work | Throughput | Wall time | CPU hours |
|---|---:|---:|---:|---:|
| Recoverability | 30,600 units / 42,840 rollouts | 0.330456 unit/s | 1.072 days | 143.34 |
| Residual V2 | 536,000 decisions / 4,824,000 candidates | 0.243524 decision/s | 25.475 days | 5,080.11 |

Parallel efficiency at W12 is 0.5214 and peak aggregate worker RSS is
2,614,145,024 bytes. Recoverability is operationally qualified. Residual V2 is
classified **H4_OPERATIONAL_RISK_BUT_FEASIBLE** by the criteria frozen before
results: its upper-bound wall time is greater than 14 days and no greater than
30 days, while semantic, storage, RAM, writer, and resume gates pass.

## GPU

Docker sees the NVIDIA RTX 5000 Ada Generation, UUID
`GPU-262a5f7e-fa85-a213-98ed-2761941b4e9a`, 32,760 MiB VRAM, compute capability
8.9, driver 536.96, and driver-exposed CUDA 12.2. The generation image contains
PyTorch 2.8.0 CPU and reports CUDA unavailable. Sampled NVIDIA utilization was
0-5%, but it cannot be attributed to container CUDA science because no CUDA
scientific process exists in that image.

Simulator, controller, safety, transition protocol, Target V4, recoverability,
Residual Expert V2, ego-graph construction, and generation-time model work
remain CPU-authoritative. The GPU is reserved for later training qualification.

## Authorization

| Scope | Status |
|---|---|
| RECOVERABILITY_GENERATION | `AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION` |
| RESIDUAL_V2_GENERATION | `AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION` |
| STUDY_A_TRAIN_VALIDATION | `AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION` |
| STUDY_A_N24_ZERO_SHOT | `SEALED_NOT_AUTHORIZED` |
| STUDY_B | `AUTHORIZED_ON_EXPLICIT_OWNER_INSTRUCTION` |
| FINAL_TEST | `SEALED_NOT_AUTHORIZED` |

There is no universal authorization flag. Residual authorization carries the
recorded H4 operational risk and does not change its scientific budget.

## Manifest And Preflight

| Artifact | Canonical hash |
|---|---|
| Operational contract V2 | `204a3954de7da3d496ccd6ca9fd57757710293b4911abc83bcffce795426414a` |
| Operational job manifest V2 | `d585a1a823db980d8a166a16b6596ba41e49c1491594acda8d667b57f0bcb21b` |
| Authorization scope V2 | `5b5533277e2789fcb66dfc0de5f44102a33924492d57f2d90099e4eab4d9a015` |
| Operational preflight V2 | `e9f683910de30ff9af60d76182f30fe00e21a68b5e1806a2bbad865531233500` |
| Final readiness root V2 | `089552354f74f7cb84b6831bf394328d58734ff17d60f79e30a498dfaee39117` |

The positive preflight passes 22 checks. The negative matrix rejects all 15
predeclared cases: wrong host, image, source, worker count, nested threads,
chunk, timeout, resume contract, staging mode, Study A N24 access, final-test
access, infeasible H4 authorization, scientific root, portability root, and a
broad authorization flag. Escapes: **0**.

## Command Plan

The command plan is prepared and held for explicit owner instruction. It
contains eight immutable launch specifications separated by Study A / Study B,
train / validation, and recoverability / residual V2. Every selector starts in
STAGING and pins the exact image, W12, one numeric thread, C1, 1200 s
infrastructure timeout, zero semantic retries, and one infrastructure retry.

Prepared: **YES**. Executed: **NO**.

No Study A N24 command and no final-test command were created.

## Isolation

| Counter | Value |
|---|---:|
| Study A N24 accesses | 0 |
| Final-test accesses | 0 |
| Official recoverability rows | 0 |
| Official residual rows | 0 |
| Official shards | 0 |
| Checkpoints | 0 |
| Optimizer states | 0 |
| Training operations | 0 |

RB21-TARGET stops here. Official generation remains held until a new explicit
owner instruction.
