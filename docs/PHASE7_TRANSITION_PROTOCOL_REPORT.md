# Phase 7 Transition Protocol Report

## Scope and implementation

Approved source baseline:
`5f23666d872aa45258ffef78f0651b45c000fc2d`.

The implementation adds schema `rvt-transition-protocol/v1`, five immutable
versioned wire messages, canonical originator-independent intent identity,
duplicate-suppressed neighbour flooding, distributed-min synthetic score
agreement, robot-local swept-envelope readiness, fixed-membership all-ready and
confirmation, synchronized local commitment, Phase 6 controller/safety
execution, local-dwell status agreement, abort/rearm, and actual frame-byte
accounting.  `transition_protocol_v1_enabled` remains false by default.

State progression is:

`STABLE_TOPOLOGY -> INTENT_ACTIVE -> CANDIDATE_SCORE_AGREEMENT ->
WAITING_FOR_LOCAL_READINESS -> ALL_READY_AGREEMENT ->
TOPOLOGY_CONFIRMATION -> TOPOLOGY_COMMITTED -> TRANSITION_EXECUTION ->
TARGET_DWELL -> COMPLETE -> REARMED`, with explicit aborts.

The score rule was frozen before evaluation as distributed minimum.  The
readiness state is SAFE only when source/lifecycle, dynamic observation extent,
local obstacle capsule clearance, fresh one-hop peer compatibility, Phase 6
action bounds, and safety-projection status are all known and valid.  UNSAFE or
UNKNOWN blocks all-ready.

## Qualification result

- Open space: 47/144 target-dwell completions, 144/144 collision-free.
- Reliable N/pair cells: 10/36; rejected/unreliable cells: 26/36.
- Remaining failures: 97 `safety_projection_failure` emergency aborts before
  integrating an infeasible action.
- Geometric readiness: 0/48 false SAFE, 0/48 false UNSAFE, 4/48 UNKNOWN.
- Historical premature widening: blocked; centre SAFE cannot override four
  constrained outer roles; zero mode epochs.
- Constriction: 0 premature commitments; eventual-safe and restored-link
  fixtures proceed in the same lifecycle; infeasible/incomplete fixtures abort.
- Connected communication: 30/30 cells complete intent, score, readiness, and
  confirmation agreement; zero partial commitment.
- Temporary disconnection: 5/5 contract violations detected, zero commits.
- Epochs: zero source-to-source, no-op, retry, or duplicate-created epochs;
  every committed episode has exactly one mode epoch.
- Message cost: all figures come from serializer frame lengths.  Open-matrix
  totals are 5,185,812 intent; 88,423,368 score; 98,951,663 readiness;
  84,947,976 confirmation; and 19,938,778 status bytes.
- Scaling: path communication latency grows from 2.4 s at N5/D4 to 13.8 s at
  N24/D23; path bytes grow from 77,454 to 7,982,488.  N24 complete-graph
  diagnostic is 0.6 s and 29,203 bytes.
- Strict guards: zero global decision, readiness, exit plane, centroid, joint
  action, partial commitment, or forbidden model-path violations.
- Learned isolation: zero Phase 5 calls, zero residual calls, zero training
  runs, zero scientific labels, and zero final-test layout accesses.

## Gate decision

| gate | result | evidence |
|---|---|---|
| P7-G1 strict decentralization | PASS | zero strict violations; delivery schedulers are named offline boundaries |
| P7-G2 intent semantics | PASS | topology unchanged before commit; duplicate event creates no epoch |
| P7-G3 readiness safety | PASS | false-SAFE 0; every premature fixture blocked |
| P7-G4 agreement | PASS | 30/30 connected graph cells; no partial commitment |
| P7-G5 open-space transitions | **FAIL** | dwell 47/144; only 10/36 cells meet per-cell reliability |
| P7-G6 constriction safety | PASS | premature widening 0; infeasible fixtures abort safely |
| P7-G7 epoch control | PASS | no-op/retry/source-equals-target epochs 0 |
| P7-G8 variable size | PASS WITH REJECTIONS | mechanics reported through N24; failed cells explicit |
| P7-G9 communication contract | PASS | all k values meet D; five violations detected |
| P7-G10 byte accounting | PASS | bytes accepted only as serialized frames |
| P7-G11 runtime preservation | PASS | learned/residual/training/final-test accesses 0 |

Acceptance criteria A1-A6 and A8-A11 pass.  A7's decentralization and emergency
safety behavior pass, but reliable closed-loop transition execution does not.

## Corrections during Phase 7

Four behavior-affecting protocol corrections were made before the frozen rerun:

1. intent validity was extended by the derived causal propagation duration;
2. incomplete sensing was kept UNKNOWN rather than reinterpreted as an obstacle;
3. an infeasible Phase 6 projection now emergency-aborts before action
   integration;
4. local target dwell no longer marks whole-team COMPLETE until fixed-membership
   completion-status flooding agrees.

The guard inventory was extended to identify the new simulator delivery and
qualification modules as explicit offline boundaries while continuing to scan
the robot-local state machine and readiness implementation.  No correction
changed topology geometry, controller/safety equations or gains, Metric V3,
epsilon, physical parameters, residual bounds, or a historical result.

## Artifacts and tests

Created: 6 Phase 7 implementation modules, 1 runner, 20 required test modules,
21 required documents, and the `results/phase7_transition_protocol/` JSON
tree.  Modified existing implementation: `decentralized/guards.py` only, to
classify the named simulator boundaries.  The approved baseline had 1,471
tests; Phase 7 adds 361, for 1,832 total.  The clean-checkout result and exact
Phase 7 commit are reported with the completion handoff.

## Historical impact and next blocker

Historical results are unchanged.  The all-ready mechanism repairs the known
common-KEEP authorization defect, but the full three-topology transition claim
is blocked by the unchanged Phase 6 safety projection becoming infeasible
during role motion in 97 episodes.  Phase 8 learned selection must not begin as
though these transitions were mechanically reliable.  The next approved work
must determine whether the failing role trajectories are unsupported geometry
or require a controller/safety repair under a separately declared scope.

## Verdict

**C. Readiness is valid, but one or more required topology-pair/team-size cells
are mechanically unreliable.**
