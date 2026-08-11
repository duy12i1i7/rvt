# Phase 9G0-R Pre-Data Official Generation Closure

## Result

Phase 9G0-R closes the six owner-approved scientific bindings and supplies real
official recoverability and Residual Expert V2 producers. No official data was
generated. The executable source is commit
`8cf64481cd17b2c44f7007d3722a8110e53cae46`; the target-qualified superseding
image is
`sha256:5e13c21aaa20f2ac02eff36172aea467720b9c925d13882708e3e90686655d9c`.

The official command plan is prepared but held. Every narrow authorization
artifact contains `official_generation_execution_authorized=false`, and all
eight commands were resolved with `--resolve-only`. No command entered
scientific execution or wrote STAGING.

## Owner Addendum

The additive addendum hash is
`523d865cf04b7a5bd2a9cec8cb9a105fd5ef1f1476f6acec34e8cd47cf0dcad0`.
It freezes, prospectively:

1. recoverability scientific row identity;
2. by-value robot-local ego-graph content;
3. scientific rollout-configuration hash;
4. lifecycle and communication hash preimages;
5. atomic COMPACT/LINE candidate-pair reconciliation;
6. residual dense-state universe and deterministic K=16 retention.

Before the addendum there were zero official rows, run IDs, STAGING writes,
Study A N24 accesses, and final-test accesses. The decisions therefore precede
all official labels and cannot depend on observed official outcomes.

## Row Identity

`rvt-recoverability-row-identity/v1` hashes project-canonical JSON containing
exactly:

`schema`, `study`, `split`, `family`, `layout_sha256`, `team_size`,
`episode_id`, `timestep`, `robot_id`, `candidate_topology_id`,
`graph_fingerprint`, `target_v4_contract_sha256`, and
`recoverability_row_binding_spec_sha256`.

Labels, replica index, worker/chunk/retry/order, wall clock, paths, timeout, and
infrastructure metadata are excluded. Tests prove scheduling and diagnostic
label interventions leave the ID unchanged, while robot, candidate, graph, and
layout changes alter it.

## Ego Graph

Each row stores the exact canonical `RobotLocalEgoGraph` model input by value.
The graph fingerprint covers versions, units, local mission metadata including
`mission_orientation_cos_sin`, all node tensors/masks/kinds, and all edge
tensors/masks/types. The explicit candidate topology remains a separate row
field. Node dimension 35 and edge dimension 19 are unchanged.

Round-trip tests reproduce every model-input tensor exactly. Locality checks
admit one `RobotView` and its local topology slice only. No global pooled graph,
global centroid, full-swarm state, or inaccessible neighbor-of-neighbor feature
is present.

## Rollout Configuration

`rvt-official-rollout-configuration/v1` binds study, split, family, layout,
team size, episode/event/timestep, candidate, scientific replica, matched seed
and stream, frozen source-policy/topology/controller/transition/safety/simulator
and Target V4 contracts, runtime integration, lifecycle hash, and communication
hash. It uses canonical JSON, not Python `repr`.

Worker count/ID, chunk size/ID, attempt index, wall clock, Docker/output paths,
timeout, and retry state are excluded. Scheduling changes therefore do not
change the scientific rollout hash.

## Lifecycle And Communication

Lifecycle preimages come from complete canonical `RuntimeConfig.for_team_size`
scientific sections (`physical`, `mission`, `formation`, `sensing`, `protocol`,
`controller`, `safety`) and `TransitionProtocolRuntimeOptions`. The contract
hash is `750e6c576ac89c91c0028051e8a1684e4db7abe4419b0be1c42a7958b3b454a6`.

Communication preimages come from `RuntimeConfig.communication`, the compiled
`ScenarioRuntimeBinding.communication_contract`, the source-job communication
seed, and the corresponding `CounterStream` identity. The contract hash is
`fcca7874958457414f05a64519a1ad3d2cb6036b0385de663eed73b5a15c569a`.
Field-level provenance is recorded in the two contract artifacts. No
behavior-affecting field remains unresolved.

## Candidate Pair

The decision event is the publication boundary. COMPACT and LINE use matched
replicas; F8/F9 use exactly three and all-success aggregation. A labelable pair
publishes exactly `2*N` prospective robot-local rows in one transaction. If
either aggregate is `GENERATION_INVALID`, the transaction reconciles with zero
training rows. An unresolved infrastructure exception receives one identical
retry and cannot be scientifically reconciled as a negative or partial pair.

The canary observed valid positive and valid negative aggregates, F8/F9 three
replicas, exact `2*N` row sets, and atomic zero-row invalid pairs.

## Residual Retention

The universe is every valid, nonterminal robot-local control decision instant
where the existing base action, local safety context, and Residual Expert V2
snapshot are constructible. It does not inspect labels, utilities, future
outcomes, collision, success, difficulty, or class balance.

For each episode and robot, K=16 uses integer indices
`floor(j*(M-1)/15)` for `j=0..15` when `M>16`; otherwise it retains all M. The
original timestep is preserved. Exact tests cover M=0, 1, 2, 15, 16, 17, 32,
and 100 and prove deterministic first/last inclusion and unique monotonic
indices.

Authorized manifests contain 32,560 robot-episodes. The strict upper bound is
520,960 attempted states, below the exact 536,000 cap by 15,040. Study A N24
and final test are excluded; authorized Study B N24 remains included only in
Study B.

## Randomness And Scope

The preserved authority is `rvt_swarm.phase9c.manifest._replica_seeds`. The
exact regression checked 21,000 nonsealed event/replica comparison groups with
zero COMPACT/LINE seed mismatch. All 3,000 F8/F9 events retained three distinct
matched replica seeds.

The compiler covers F1-F10, Study A train/validation, and Study B
train/validation including its authorized N24 cells. Study A N24 and final test
remain reject-only and were not enumerated or accessed.

## Producers And Replay

The recoverability entry point is
`rvt_swarm.phase9g0r.producer.produce_recoverability_event`; the residual entry
point is `rvt_swarm.phase9g0r.producer.produce_residual_state`; the writer is
`rvt_swarm.phase9g0r.writer.CanonicalGenerationWriter`. Writer modes are only
`DIAGNOSTIC` and authorized `OFFICIAL_STAGING`; no direct FINAL writer exists.

The diagnostic canary covers F1, F2, F5, F8, F9, F10 and N=5, 6, 8, 12, 16,
plus residual `LABELED` and naturally encountered `NO_ELIGIBLE_ACTION` cases.
The RB20 replay reproduced 4 source episodes, 14 recoverability rollouts, and
36 residual candidates with zero semantic or frozen-identity mismatch.

## Command Plan And Performance

Command Plan V2 hash is
`473fc5243e3a11afbb44df868a0d3c814f7e534bb57439b85a2e79d27c4856f0`.
All eight study/split/branch commands bind the source commit, exact image,
addendum, provenance root, job manifest, STAGING namespace, and narrow
authorization scope. Commands executed: **NO**.

The real production path is classified
`RB21_PRODUCTION_PATH_REQUALIFICATION_REQUIRED`. RB21 did not benchmark the new
F1-F10 compiler, `2*N` materialization/reconciliation, K=16 trajectory scan, or
canonical publication units. The old W=12/thread=1/chunk=1/1200-second profile
is not authoritative and was not automatically restored. This is an
operational qualification requirement, not a scientific blocker.

## Target And Tests

AVIS `100.71.102.9` was reached. The old qualified image was present. The final
image was built directly from it with committed source, exact Git HEAD, correct
runtime ownership, and no macOS AppleDouble files.

- Focused required regression: 133 passed.
- Local complete suite: 3,040 passed, 0 failed, 0 xfailed.
- Target packaging regression: 149 passed.
- Exact-image target complete suite: 3,034 passed, 0 failed, 0 xfailed.
- Final evidence tests inside the exact image: 6 passed, 0 failed.
- Negative preflight: 30 cases, zero escapes.
- Command resolutions: 8, zero scientific executions.

The single warning is the previously known PyTorch tensor-to-scalar warning.

## Isolation

At closure: official run IDs, STAGING writes, recoverability rows, residual
rows, shards, training operations, checkpoints, optimizer states, Study A N24
accesses, and final-test accesses are all zero.

## Verdict

**C. The pre-data scientific addendum and executable official generation
binding are closed. The actual production path requires a scoped RB21
performance requalification before a new narrow execution authorization may be
issued.**
