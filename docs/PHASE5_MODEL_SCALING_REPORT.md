# Phase 5 Model Scaling Report

## Scope and platform

This report contains graph-construction and untrained forward-pass
microbenchmarks only. It does not step a mission environment, generate labels,
train on trajectories, evaluate task success, qualify COMPACT, or access final
test layouts.

Platform: Apple M4 Pro arm64, Python 3.9.6, PyTorch 2.8.0, one CPU thread,
float32, evaluation mode, no gradients. The model seed is fixed only for
repeatable architecture timing. Each robot is evaluated for KEEP, COMPACT, and
LINE. Bounded-degree cases use four peers and zero to three local obstacles.

Default model counts:

| Component | Parameters |
|---|---:|
| encoder | 230,976 |
| candidate conditioner | 22,144 |
| recoverability head | 9,409 |
| residual head | 9,506 |
| total | 272,035 |

Parameters plus persistent buffers occupy 1,088,172 bytes. Output tensors use
33 bytes per candidate: two int64 IDs, float32 logit and probability, two
float32 residuals, and one Boolean validity flag.

## Bounded-degree results

`construct/robot` builds three candidate graphs sequentially. `forward/cand`
is one candidate in an individual local call. `forward/robot` evaluates all
three candidates in one local batch. `sim forward` is one centralized simulator
batch of all 3N independent graphs. `combined/robot` is local three-graph
construction plus local three-candidate forward.

| N | Graphs | Candidate evals | Peer avg | Obs avg | Edge avg | Construct/robot ms | Forward/cand ms | Forward/robot ms | Sim forward ms | Combined/robot ms | Input tensor bytes | Peak operator alloc bytes |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 5 | 15 | 4 | 1.200 | 10.400 | 7.4177 | 0.3860 | 0.4236 | 0.6462 | 7.8414 | 38,184 | 239,616 |
| 6 | 6 | 18 | 4 | 1.167 | 10.333 | 7.9830 | 0.3881 | 0.4368 | 0.7164 | 8.4198 | 45,552 | 285,696 |
| 8 | 8 | 24 | 4 | 1.500 | 11.000 | 9.2501 | 0.3811 | 0.4252 | 0.7920 | 9.6753 | 64,320 | 405,504 |
| 12 | 12 | 36 | 4 | 1.500 | 11.000 | 11.8375 | 0.3833 | 0.4298 | 0.9688 | 12.2673 | 96,480 | 608,256 |
| 16 | 16 | 48 | 4 | 1.500 | 11.000 | 14.3335 | 0.3771 | 0.4199 | 1.1565 | 14.7534 | 128,640 | 811,008 |
| 24 | 24 | 72 | 4 | 1.500 | 11.000 | 19.5195 | 0.3747 | 0.4201 | 1.4681 | 19.9396 | 192,960 | 1,216,512 |

The local model-forward cost remains approximately constant under bounded local
degree. Sequential graph construction dominates combined cost and grows in this
Python simulator implementation. Central batched simulator forward is faster
than N independent calls, but it remains a test harness optimization, not a
centralized deployment claim.

## Local density sensitivity at N=24

The table holds one dimension at a representative value while evaluating all
three candidates for one robot.

| Peers | Obstacles | Edges/graph | Forward/robot ms | Input tensor bytes |
|---:|---:|---:|---:|---:|
| 0 | 0 | 0 | 0.1677 | 648 |
| 0 | 1 | 2 | 0.3783 | 1,992 |
| 0 | 3 | 6 | 0.3933 | 4,680 |
| 0 | 6 | 12 | 0.4301 | 8,712 |
| 1 | 1 | 4 | 0.3815 | 3,336 |
| 2 | 1 | 6 | 0.3847 | 4,680 |
| 4 | 1 | 10 | 0.4144 | 7,368 |
| 8 | 1 | 18 | 0.4667 | 12,744 |
| 23 | 1 | 48 | 0.6261 | 32,904 |

With 23 peers and 6 obstacles, three-candidate forward is 0.6561 ms and input
tensors use 39,624 bytes for one robot.

## Dense N=24 simulator diagnostic

The complete graph is diagnostic stress only. For all 24 robots and all 72
candidate graphs it has 23 peers, 1.5 obstacles, and 49 edges per graph on
average. Measured totals are:

- graph construction: 2,348.0056 ms total, 97.8336 ms per robot for all
  candidates;
- model forward in one simulator batch: 5.0105 ms total, 0.2088 ms amortized
  per robot;
- combined simulator total: 2,353.0161 ms;
- input batch tensors: 805,824 bytes.

The dense case is not a deployment assumption. N=24 remains mechanically
tested only. No real-time claim is made: combined future runtime cost must be
measured with the eventual runtime integration and compared against the
configured control period.
