# Phase 9C Runtime Binding Report

## Scope

Phase 9C-RB began from blocked Phase 9 commit
`84f48dfd9244793cd7559e5a0b917292168b384e` on branch
`research/rvt-phase9-runtime-binding-v1`. The blocked commit is tagged
`rvt-phase9-generation-binding-blocked-v1`.

The accepted immutable references remain:

| Reference | SHA-256/commit |
|---|---|
| Phase 8 experiment protocol | `0bb68dd56ef0837f83c44dcf5281498f8c0ea934b00bbb9b3d3f298264d32147` |
| Phase 9B generation budget | `3853b8ad4484d733de9be7d0e27bf273f33e14054f3089f6b5454cc17815846e` |
| Composite generation protocol | `d928a7f614434b4d99395c5b75398b6277ec407cbf206e332a621f553022be57` |
| Frozen job manifest | `801fe4e2bd694da0dda7c310226906e59d9bc5435d657fab2e3f132432aa2dc3` |
| Approved Phase 9B commit | `20a7541a4ae946c2ca051cde0c353c396d2c1241` |

## RB-1 result

The exact field and runtime-input inventory is in
`docs/PHASE9C_SCENARIO_RUNTIME_BINDING_INVENTORY.md`. It found six blocking
groups of Category D values:

1. Phase 8 corridor and bypass descriptors do not uniquely define executable
   collision and sensor geometry.
2. F9 canonical obstacle speed disagrees with its timestamped waypoint speed,
   and no precedence or evolution rule is frozen.
3. F8 communication profiles do not uniquely define delay, loss, disconnection,
   restoration, or affected-link schedules.
4. Approved seed identities do not define scientific perturbation and
   disturbance generators.
5. S0, S3, S4 and S5 do not have complete approved executable policy semantics.
6. Target V4 names outcome conditions but does not completely define the runtime
   predicates needed to evaluate them.

The start origin, goal, initial COMPACT topology, persistent role offsets,
goal-aligned mission heading, and horizon are uniquely bindable. That partial
mapping is insufficient because RB-1 explicitly prohibits implementation while
any required value is Category D.

## Work intentionally not performed

No binding schema, publication executor, Phase 7 session adapter, simulator
snapshot, candidate clone, disturbance provider, dynamic-obstacle provider,
S0-S5 implementation, candidate executor, binding manifest, or execution
manifest was created. The Phase 9C structural canary was not run. Full dataset
generation, model training, DAgger, Study A N=24 access and final-test access all
remain zero.

The legacy `start_center` dependency was not patched and the legacy KEEP/LINE
runtime was not promoted. Existing Phase 8/9B manifests, blocked-run artifacts,
failed canary attempts and scientific code remain unchanged.

## Acceptance gates

| Gate | Result | Reason |
|---|---|---|
| RB-G1 complete field binding | BLOCKED | Required Category D values remain |
| RB-G2 no legacy dependency | NOT_EVALUATED | No publication executor was implemented |
| RB-G3 COMPACT/LINE execution | NOT_EVALUATED | No scientific session exists |
| RB-G4 source policy completeness | BLOCKED | S0/S3/S4/S5 semantics are incomplete |
| RB-G5 matched cloning | NOT_EVALUATED | No source snapshot exists |
| RB-G6 stream matching | NOT_EVALUATED | Stream generators are not specified |
| RB-G7 robot locality | NOT_EVALUATED | No new runtime path exists |
| RB-G8 protocol equivalence | NOT_EVALUATED | No adapter was implemented |
| RB-G9 structural canary | NOT_RUN | RB-1 stop rule |
| RB-G10 reproducibility | NOT_EVALUATED | Canary not run |
| RB-G11 final-test isolation | PASS | Final-test runtime access count remains zero |
| RB-G12 no scientific generation | PASS | No dataset/checkpoint/optimizer artifact was created |

## Verification

The repository collected 2,025 tests before this phase and 2,029 afterward. The
four added stop-audit tests passed, the focused Phase 6/7 equivalence and scope
guards passed, and the complete suite passed `2029 passed` with one pre-existing
PyTorch warning in 203.98 seconds.

The preserved blocked-run files retained these byte hashes after the suite:

| Preserved artifact | File SHA-256 |
|---|---|
| Phase 9 canary audit | `1d3be3ba5d34a24fd78405f68f6e0978bc93f7a4685b339a24182b3ee371c040` |
| Phase 9 generation report | `535f5c109e4695101fb0b0a31a1eaca1a4533a2880b2efcb81b0dd127f98eeaa` |
| Phase 9 failure attribution | `25de32d8383db0e35c9c2f781b93dde0fa7d2a94668d9aad1c5827240a7a909d` |
| Frozen job-manifest file | `9d094d7dca34e2daf8edc05c018d0372d7c4d2219a710032a6b066be494ea49f` |

No `scenario_runtime_binding_v1.json`, `phase9_execution_protocol_v1.json`, full
dataset shard, trained checkpoint, or optimizer state exists. Study A N=24 and
final-test runtime access counts remain zero.

## Required resolution before another binding attempt

An approved protocol amendment must freeze, without inspecting final-test data:

- exact executable boundary/collision/sensor semantics for every static primitive;
- one authoritative F9 motion representation and complete time evolution;
- exact F8 communication schedule semantics;
- scientific initial-condition and disturbance generators for existing seeds;
- complete S0/S3/S4/S5 behavior; and
- executable predicates for every Target V4 condition.

After those semantics are frozen, a new phase may implement the engineering
binding without changing layouts, jobs, budgets, seeds, controller, safety or
transition mechanics.

## Verdict

**A. ScenarioLayout still cannot be mapped uniquely into executable runtime semantics.**

Phase 9 full generation must remain blocked.
