# Phase 5 RVT-FD24 Model Architecture Report

## Scope and provenance

Approved base: Phase 4 commit
`6f23ca180d964bf55750ba2e7397de13b3e4de3c` on
`research/rvt-swarm-fd24-v1`. Phase 5 implemented only the mechanically tested
robot-local model architecture, strict checkpoint contract, and disabled shadow
adapter.

No topology geometry/ID, ego graph feature/order/hash, controller gain, Metric
V3 definition, communication protocol, topology decision, physical/mission
parameter, historical checkpoint, or historical result changed. No scientific
training, recoverability labels, expert action data, trajectory learning,
COMPACT closed-loop qualification, scenario construction, final-test access, or
manuscript quantitative result was performed.

## Delivered architecture

- Model schema: `rvt-fd24-model/v1`.
- Accepted graph: `rvt-ego-graph/v2`, widths 35/19.
- Accepted feature hash:
  `1ea52c6aebb23360641ce6a09ef41d2d21fd372f2744f196b91ff184a1a2cf5b`.
- Accepted topology registry: `rvt-topology-registry/v1`.
- Explicit vocabulary: KEEP 0, COMPACT 5, LINE 2.
- Three typed node projections, four typed edge projections, three local
  message blocks, and SELF/root readout.
- One shared candidate conditioner using equality-mapped topology embedding and
  observer-local candidate geometry.
- One robot-local recoverability-evidence logit and sigmoid convenience value.
- One two-dimensional residual head bounded by per-component immutable limits.
- Closed typed input/output structures and canonical graph association.
- Versioned strict checkpoint save/load with state-dict content hash.
- Separate `direct_local_action_ablation` head interface, absent from the
  primary model.
- Disabled-by-default shadow adapter with no import into current runtime.
- Strict guard coverage extended to the FD24 namespace.

Default parameter counts:

| Component | Parameters |
|---|---:|
| encoder | 230,976 |
| candidate conditioner | 22,144 |
| recoverability head | 9,409 |
| residual-action head | 9,506 |
| total | 272,035 |

The residual action dimension is derived from the named planar controller
action components. Default bounds are `(0.15, 0.15) m/s^2`, each derived as
0.25 of immutable maximum acceleration. The output is one residual per ego
graph, never one action per peer or a joint team action.

## Verification

The approved Phase 4 suite collected 1202 tests. Phase 5 collects 1329, adding
127 tests. The final working-tree full run completed with
`1329 passed, 1 warning` in 63.49 seconds. The warning is the pre-existing
PyTorch scalar-conversion warning in `tests/test_simplified_model.py`.

The 15 required Phase 5 test files plus strict/no-magic guards collect 154
tests. Direct audits report:

| Audit | Result |
|---|---:|
| strict runtime violations across decentralized and FD24 namespaces | 0 |
| global graph/model import or pooling violations | 0 |
| joint-action path violations | 0 |
| unexplained deployable constants | 0 |
| unobserved/evaluation intervention cases | 7/7 exact invariant |
| batch isolation additions/orders/candidates | exact within predeclared tolerance |
| node/edge/candidate permutation tests | pass at fixed `1e-6` tolerance |
| required N x candidate forward/backward matrix | 6 x 3 pass |
| checkpoint rejection matrix | all declared incompatibilities rejected |

Gradient tests produced finite nonzero gradients in all three node-type
projections, all four edge-type projections, every message block, candidate ID
embedding, local candidate metadata projection, recoverability head, and
residual head. Zero-peer, zero-obstacle, mixed local entities, extreme finite
features, and dense N=24 synthetic inputs remained finite.

The deterministic three-sample synthetic micro-overfit reduced its synthetic
loss from `0.997744143` to `0.000024584` in 80 fixed steps, ratio
`0.000024640`. This verifies implementation capacity only and is not scientific
training or recoverability evidence.

## Checkpoint compatibility matrix

| Source | Load as FD24 | Reason |
|---|---|---|
| exact `rvt-fd24-checkpoint/v1` | yes | all schema, config, vocabulary, bounds and tensor hashes match |
| global 68/11 checkpoints | no | global semantics and wrong feature widths |
| decentralized V1 28/9 checkpoints | no | feature/mask/edge/candidate contract differs |
| legacy width-three `[0,2,3]` topology heads | no | COMPACT 5 is absent; positional meaning conflicts |
| binary KEEP/LINE checkpoints | no | incomplete candidate vocabulary |
| tampered state dict | no | canonical state hash mismatch |
| changed runtime/model config | no | canonical hash or residual-bound mismatch |
| global information-scope checkpoint | no | exact local scope required |

Historical models and checkpoint readers remain available only through their
existing compatibility/diagnostic paths. No weight was partially loaded into
FD24.

## Scaling summary

Detailed measurements are in `PHASE5_MODEL_SCALING_REPORT.md`. Under bounded
degree, three-candidate local forward is 0.4199 to 0.4368 ms/robot across
N=5..24. N=24 central simulator batch forward is 1.4681 ms for 72 independent
candidate graphs. Input tensors use 192,960 bytes and the largest profiled
single-operator allocation is 1,216,512 bytes.

Graph construction dominates combined local cost: 7.8414 ms/robot at N=5 and
19.9396 ms/robot at N=24 bounded degree. Dense N=24 is a stress diagnostic:
2,348.0056 ms graph construction plus 5.0105 ms model forward for all 72
candidate graphs. No real-time or scientific N=24 claim is made.

## Runtime and scope impact

Shadow status: implemented, disabled by default, diagnostics only. Active
`_robot_decision`: unchanged and still uses ego graph V1. Topology selection,
controller action, communication, lifecycle, and historical experiment output:
unchanged.

Phase 6 remains blocked on approved scientific data/label protocols, actual
training and calibration, future base-action plus residual integration,
distributed score semantics, and later readiness/safety mechanisms. COMPACT is
still not closed-loop qualified, and N=24 remains mechanically tested only.

## Acceptance gates

| Gate | Result |
|---|---|
| P5-G1 authoritative local model | pass |
| P5-G2 shared candidate conditioning | pass |
| P5-G3 local recoverability evidence | pass |
| P5-G4 robot-local bounded residual | pass |
| P5-G5 no joint action | pass |
| P5-G6 strict locality | pass |
| P5-G7 batch isolation | pass |
| P5-G8 variable size through N=24 | pass mechanically |
| P5-G9 numerical and gradient validity | pass |
| P5-G10 checkpoint safety | pass |
| P5-G11 scaling report | pass |
| P5-G12 runtime preservation | pass |
| P5-G13 legacy isolation | pass |
| P5-G14 scope control | pass |

## Verdict

C. The robot-local RVT-FD24 architecture is mechanically valid; proceed to
Phase 6.
