# Phase 6 Controller Scaling Report

The benchmark measures the complete forced-topology robot-local stack with the
Phase 5 model inactive: received-message ingestion, local obstacle processing,
typed input construction, registry offset lookup, base controller, exact local
safety projection and final physical clipping. Each cell contains 100 repeated
iterations under `tracemalloc` using the repository `.venv` on the audit host.

The configured control period is 150 ms. Under range-bounded deployable message
input with one local obstacle, the worst median per-robot latency was 5.498 ms
and the worst p95 was 7.664 ms at N=24. The result is **comfortably within the
period** for this Phase 6 stack. This is not a complete RVT real-time claim:
neural inference, consensus and transition protocols are inactive.

## Range-bounded deployable input

`Degree` is the median count of received one-hop peers. `Discovery` and
`aggregate` belong to centralized simulator orchestration; the other timings
are per robot. Memory is process-level peak traced allocation for the benchmark
cell, not per-robot resident memory.

| N | Degree | median (ms) | p95 (ms) | p99 (ms) | projection (ms) | intervention (ms) | discovery (ms) | aggregate (ms) | peak bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 4 | 1.318 | 1.603 | 1.739 | 1.126 | 1.126 | 0.260 | 16.493 | 532305 |
| 6 | 5 | 1.502 | 1.864 | 2.052 | 1.300 | 1.300 | 0.370 | 22.667 | 273021 |
| 8 | 7 | 1.934 | 2.378 | 2.596 | 1.707 | 1.707 | 0.689 | 38.432 | 497320 |
| 12 | 11 | 3.078 | 3.465 | 3.616 | 2.819 | 2.819 | 1.636 | 88.057 | 1004052 |
| 16 | 14 | 4.116 | 4.713 | 4.918 | 3.811 | 3.811 | 2.694 | 155.623 | 1414963 |
| 24 | 16 | 5.498 | 7.664 | 8.079 | 5.134 | 5.134 | 5.374 | 328.064 | 1257099 |

The centralized sequential aggregate exceeds one 150 ms period at N=16 and
N=24. This is reported as simulator infrastructure cost, not hidden inside the
deployable latency. A deployment invokes one local controller on each robot and
does not serialize all N controllers in one process.

## Dense diagnostic stress

Dense complete communication is not a deployable topology assumption. It
stresses message ingestion and local safety constraints only.

| N | Degree | median (ms) | p95 (ms) | p99 (ms) | projection (ms) | discovery (ms) | aggregate (ms) | peak bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 4 | 1.309 | 1.593 | 1.713 | 1.122 | 0.196 | 16.363 | 183913 |
| 6 | 5 | 1.504 | 1.913 | 2.083 | 1.300 | 0.284 | 22.683 | 115119 |
| 8 | 7 | 1.937 | 2.345 | 2.485 | 1.715 | 0.526 | 38.304 | 201480 |
| 12 | 11 | 2.991 | 3.353 | 3.532 | 2.722 | 1.207 | 85.253 | 326300 |
| 16 | 15 | 4.101 | 4.613 | 4.765 | 3.791 | 2.127 | 153.367 | 690451 |
| 24 | 23 | 5.705 | 7.901 | 8.272 | 5.301 | 5.222 | 340.558 | 1525227 |

## Local obstacle count at N=24

| Obstacles | Degree | median (ms) | p95 (ms) | p99 (ms) | projection (ms) | intervention (ms) | aggregate (ms) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 16 | 5.128 | 7.246 | 7.617 | 4.872 | n/a | 262.241 |
| 1 | 16 | 5.498 | 7.664 | 8.079 | 5.134 | 5.134 | 328.064 |
| 4 | 16 | 6.721 | 9.264 | 9.671 | 6.247 | 6.247 | 390.441 |

The exact two-dimensional active-set projection dominates local latency. With
`m` local peer/obstacle half-spaces, candidate enumeration is quadratic and its
straightforward feasibility checks give an O(m^3) worst-case implementation.
The measured N=24 range-bounded and dense cases remain far below the control
period, but this Phase 6 result does not extrapolate beyond the declared N and
local-obstacle ranges.
