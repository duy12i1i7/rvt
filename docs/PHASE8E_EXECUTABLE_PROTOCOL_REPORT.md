# Phase 8E Executable Protocol Completion Report

## Scope and provenance

Phase 8E-PC is an additive, specification-only completion of the approved Phase
8 protocol. It began from blocked binding-audit commit
`62698414a9e2f0f1b388d1e9ee6401964862d86e` on branch
`research/rvt-executable-protocol-completion-v1`. The blocked audit is tagged
`rvt-phase9-runtime-binding-ambiguous-v1`.

| Frozen parent | Identity |
|---|---|
| Phase 8 protocol commit | `c17081fe1cf58cc2d3f929e35ff4bca811c75c58` |
| Phase 8 experiment protocol | `0bb68dd56ef0837f83c44dcf5281498f8c0ea934b00bbb9b3d3f298264d32147` |
| Phase 9B budget commit | `20a7541a4ae946c2ca051cde0c353c396d2c1241` |
| Phase 9B generation budget | `3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e` |
| Composite generation protocol | `d928a7f614434b4d99395c5b75398b6277ec407cbf206e332a621f553022be57` |
| Frozen Phase 9 job manifest | `801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3` |

No historical manifest, layout, budget, job identity, seed, topology, controller,
safety, transition protocol, Metric V3 or candidate set was modified.

## Immutable artifacts

| Artifact | Schema | Canonical SHA-256 |
|---|---|---|
| `executable_scientific_protocol_v1.json` | `rvt-executable-scientific-protocol/v1` | `8da0b94e5ae83cf35ea38c38504d11d6e6fdce6da09766bf8cb14c4cc252158a` |
| `source_policy_contracts_v1.json` | `rvt-source-policy-contracts/v1` | `aaf4e35a539d1ae864805ee52cfbd8be7579e7a61103e3807fbbc6d1706168df` |
| `target_v4_execution_contract_v1.json` | `rvt-target-v4-execution-contract/v1` | `54a0e0baff79fbdc320800b772f47a40ac06ac4f0e70d4fab1bf676c54b918ee` |
| per-layout records | `rvt-layout-execution-specification/v1` | one canonical hash per record |

The executable protocol rejects unknown top-level fields, missing behavioral
fields, wrong parent hashes, nonzero Category D, execution-enabled state and
invalid canonical hashes. Future generation must reference both the original
Phase 8 hash and this addendum hash.

## Completed semantics

### Geometry

World origin/bounds, mission origin, goal direction, topology origin, COMPACT
role placement, goal region, analytic circles/corridors, polyline/S passage
boundaries, F6 bypass, inflation, sensor support disks and invalidity are exact.
Every ScenarioLayout field is consumed or explicitly audit-only. The legacy
`start_center`, hidden origin/heading, KEEP runtime and headroom metadata are not
used.

Twenty train and ten validation layouts compiled: two and one per F1-F10 family,
respectively. All 30 records are canonical, uniquely hashed and have
`category_d_count=0`. No sealed final-test record was loaded or compiled.

The exact validity rule reports 13 nominal layout/team-size combinations invalid:

- N=24: train F2-00, F3-00/01, F4-00/01, F10-00/01; validation F3-00, F4-00,
  F10-00;
- N=16: train F4-00/01 and validation F4-00.

These are deterministic frozen-layout validity results, not unresolved
semantics. The corresponding scientific slot must be recorded invalid once,
without moving `start_center_meters`, resampling or replacing a job.

### Initialization and disturbances

Roles use registry order. Position perturbations are independent mission-frame
uniform components bounded by spacing margin; velocity components are bounded by
`v_max*dt`; acceleration and mutable state are initialized explicitly. Protocol
nodes begin stable with COMPACT, empty queues and zero counters. Invalid draws
are recorded without resampling.

Noise and delays are explicitly disabled unless named. Matched counterfactual
acceleration disturbance is a counter-keyed uniform disk bounded by `0.05*a_max`.
S5 has one source-only `0.25*a_max` one-step perturbation. Counter PRFs make
streams deterministic, order-independent and independently cloneable.

### F8 and F9

F8 uses a range graph updated every communication tick. Bounded delay is uniform
to the stored limit and loss is Bernoulli by directed-message counter key. The
temporary cut starts at the quantized nominal first-entry travel time, lasts
`2*(D_max+1)` ticks, partitions persistent role ordinals, drops queued cross-cut
messages and restores deterministically. It is a declared assumption-violation
stress; resulting task failure is valid negative, while schedule mismatch is
generation-invalid.

F9 uses timestamped waypoints as authoritative linear position-time motion,
holds after its final waypoint, has exact local current-state observation and
never exposes its future path. The conflicting stored speed is audit-only. This
choice rejects constant declared speed because it cannot meet frozen endpoint
times.

### Source policies

- S0: family-specific one-shot offline COMPACT/LINE script using the smooth
  profile and safety stack.
- S1: always COMPACT with Phase 6 controller and safety.
- S2: offline LINE initialization, then always LINE with no no-op epoch.
- S3: total robot-local width rule with physical/topology thresholds,
  persistence, hysteresis and UNKNOWN hold behavior; requests use Phase 7.
- S4: deterministic local diagnostic events and score 1.0 through the complete
  Phase 7 leaderless lifecycle; Phase 5 remains inactive.
- S5: S1 plus one bounded, seeded, outcome-independent robot perturbation.

All share one typed interface and exclude headroom, future state and outcomes.

### Target V4 and counterfactuals

All ten Target V4 conditions now have exact predicates, clocks, tolerances,
failure handling and precedence. Eighteen terminal causes map totally to one of
positive, valid negative or generation invalid. Runtime exceptions are typed
invalid, never implicit labels.

Candidate-equals-current holds without an epoch. A changed candidate uses Phase
7. Existing active lifecycles are preserved, not superseded for convenience.
Snapshots enumerate all physical, protocol, controller, queue, stochastic,
dynamic and mission state. Clone hash mismatch or stream mismatch invalidates the
pair without replacement.

## Acceptance gates

| Gate | Result | Evidence |
|---|---|---|
| PC-G1 zero Category D | PASS | protocol and all 30 records report zero |
| PC-G2 unique geometry | PASS | deterministic unique per-layout hashes |
| PC-G3 complete initialization | PASS | physical, protocol, queue and stream state specified |
| PC-G4 executable F8/F9 | PASS | deterministic channel schedules and waypoint motion |
| PC-G5 executable S0-S5 | PASS | six total machine-readable policies |
| PC-G6 total Target V4 | PASS | ten predicates, 18 causes, three exclusive dispositions |
| PC-G7 no legacy defaults | PASS | AST and contract guards |
| PC-G8 no post-hoc choices | PASS | no label/headroom/outcome policy inputs |
| PC-G9 final-test isolation | PASS | metadata only; geometry/runtime access zero |
| PC-G10 no execution | PASS | simulator steps, rollouts, rows and training all zero |

## Verification

The test inventory increased from 2,029 to 2,078 tests. The 49 new Phase 8E
schema, geometry, initialization, F8/F9, source-policy, Target V4,
counterfactual, compilation, locality, final-test and scope tests pass. A focused
202-test regression covering Phase 6/7 scope, configuration/no-magic guards,
split planning and final-test isolation also passes.

No simulator episode, canary, source job, candidate rollout, residual invocation,
dataset row/shard, checkpoint or optimizer state was created. Study A N=24 and
final-test runtime access counts remain zero.

## Phase 9C-RB resumption

No protocol-completeness blocker remains. Runtime binding must consume this
addendum without altering its formulas and must preserve the 13 pre-execution
nominal-invalid classifications. Phase 9C-RB still must implement and test the
binding, snapshots, clones and local observation boundary; those are engineering
work, not missing scientific choices.

## Verdict

**C. The executable scientific protocol is complete and frozen; resume Phase 9C-RB runtime-binding implementation using this addendum.**

Stop here. No runtime binding or scientific execution was performed.
