# Phase 9C-RB15-V2 — Residual Expert V2 Publication Producer Binding

**Result: the producer is bound and audited. Verdict C.**

RB-15 originally stopped because nothing *produced* `LocalActionEvaluation`
records for the frozen selector. That producer now exists, runs end to end
against the real runtime, and is pinned by 54 tests.

| artifact | hash |
|---|---|
| `results/rvt_fd24/rb15_residual_expert_binding_v2.json` | `831fde5e368ebb3b63c2d96d0734600c352f604628da7e9aab83b793ef89e7b3` |
| `results/rvt_fd24/rb15_v2_canary_v1.json` | `c09f7d20a6844cae13cd022604fe6e94b745596616a034c6285f13593f9523f4` |
| `results/rvt_fd24/residual_generation_job_identity_v2.json` | `2b0923cd5f2ca2f1b6c1f45183e0386f292e18667cd5d1f910517217c402bef4` |

Authoritative inputs consumed unchanged: spec `e3a30930…`, composite `89214 24d…`,
V1 selector, V1 target builder, the V1 dataclass at its exact eight fields, the
Phase-6 controller, the local safety projection and the frozen headroom chain.

## The path

```text
EpisodeSnapshot -> RobotView -> Phase-6 base action -> 9 residual candidates
  -> one-control-interval intervention, pre-safety
  -> matched continuation to ordinary termination
  -> utility reduction -> LocalActionEvaluation
  -> frozen V1 selector -> frozen V1 target builder
```

Two boundaries are load-bearing and are never re-implemented. The residual is
injected through `SourcePolicy.acceleration_disturbance`, which the runtime adds
to `base_action` and then re-projects with the unchanged projection — exactly
`local_safety_projection(u_base_pre_safety + delta_u_world)`. The four utility
scalars come from the frozen `phase8r.utility_v2` reducers applied to the single
matched trace.

`SimulatorEpisodeSession.local_decision_inputs` was extracted from `step` so the
producer sees the runtime's own view, controller input and controller instance
rather than a reconstruction. The refactor is behaviour-identical: nine committed
v6 policy records across three cells reproduce exactly.

## Locality is earned, not asserted

`robot_local_information_only` is a **property** derived from recorded
provenance; there is no setter and no literal `True` in the producer. Nine
action-side inputs are recorded, all in the allowed classes. Empty provenance
raises rather than defaulting to local.

Three interventions prove the boundary is real:

* **Hidden global.** Move a non-neighbour robot *after* message delivery. Robot
  i's view — built from its neighbour table, never from the joint state — is
  byte-identical, and so are the candidate set, base action, feasibility and
  provenance. Hidden truth genuinely differed.
* **One-hop.** Change a legitimate neighbour-table entry: the view hash changes
  and the base action changes with it. The hidden-global test is therefore not
  vacuous.
* **Contamination.** Inject each forbidden class in turn; the derived flag
  collapses to false and the frozen selector then rejects every candidate.

Centralized simulator truth reaches only the three `OFFLINE_LABEL_ORACLE`
utilities. `normalized_action_deviation` is `LOCAL_ACTION_INFORMATION` and is
fixed at construction time.

## Matching

All nine candidates restore the same `EpisodeSnapshot` — verified equal to the
session's own canonical hash — and share one matched exogenous stream identity.
Evaluating in reverse execution order reproduces every per-candidate hash and the
same selection, while the stored order stays canonical. Repeating the evaluation
is bit-identical.

## The canary

`RUNTIME_CONFORMANCE_ONLY`. 10 decision states across four families (F1, F5, F8,
F9), four team sizes (5, 6, 8, 12; never 24) and two source policies; **90
candidate evaluations**. 26 counterfactuals ended in collision and were scored,
not dropped; 12 candidates had their action changed by the safety projection.
No scientific dataset schema was used and no official counter moved.

**One decision state produced no expert label.** At `train-f5-00/N8` step 40 for
robot 3 the local safety projection reported `infeasible_conservative_fallback`
for every candidate including the zero residual, so the frozen eligibility
conjunction rejected all nine and the selector raised. That is the frozen
no-eligible path, and the frozen budget contract already declares the handling:
`preserve_base_and_failure_metadata_no_target_row_keep_invalid_denominator_no_replacement`.

## Performance

Measured on the canary only, single process, single worker.

| | count | mean | median | p90 | p95 | max |
|---|---:|---:|---:|---:|---:|---:|
| seconds per candidate continuation | 90 | 1.593 | 0.334 | 3.768 | 8.823 | 8.990 |
| seconds per 9-candidate evaluation | 10 | 14.34 | 3.57 | 27.31 | 27.31 | 79.71 |
| rollout control intervals | 90 | 96.7 | 65 | 89 | 471 | 474 |

Cost is dominated by rollout length, which is set by how early in the episode the
decision state sits: 9-interval continuations cost 0.25 s, 474-interval ones cost
9 s.

Projection for the frozen upper bound of **4,824,000** candidate evaluations:
single worker `1.593 × 4,824,000 ≈ 7.69 Ms ≈ 89.0 days`. For W workers,
`wall_seconds(W) = 1.593 × 4,824,000 / (W × efficiency(W))` with `efficiency(W) ≤ 1`
**unmeasured**. No worker count, no efficiency and no timeout was chosen.

Limitations are recorded in the artifact: the canary samples ten decision states
rather than the generation distribution; it never covers N=16 or N=24; parallel
efficiency was not measured; and no I/O, serialization or scheduling overhead is
included.

`RESIDUAL_V2_PERFORMANCE_STATUS = QUALIFIED_FOR_JOB_BUDGET_DESIGN` — enough to
design a job budget, not enough to choose a timeout. Not `OPERATIONAL_RISK`
because nothing failed, hung or hit the horizon guard; not
`INSUFFICIENT_BENCHMARK` because all four constraint classes, four families, four
team sizes, both policies and both collision and safety-infeasible outcomes were
exercised. **No scientific parameter was changed to improve performance**: still
9 candidates, still one control interval, still the episode remainder, unchanged
objective.

## Job identity for RB-17

A unique counterfactual evaluation needs
`(residual_cell_job_id, decision_state_id, robot_id, candidate_index,
replica_index)`, with `matched_stream_identity` and
`residual_expert_spec_v2_sha256` as verification fields. Each is justified by an
observed producer behaviour, not by assertion. The stored
`job_identity_contract.residual_cell` stops at the cell and cannot identify the
nine continuations behind one dense row. The proposal is additive; the official
manifest was not touched and no official job record was emitted.

## Scope

Official residual generation was not run and is not authorized.
`RESIDUAL_V2_GENERATION_TIMEOUT` stays `PENDING_PERFORMANCE_BENCHMARK`. RB-16 not
begun, augmentation still disabled. Recoverability rows 0, residual rows 0, shards
0, FD24 checkpoints 0, optimizer states 0, training operations 0, final-test
accesses 0, Study A N=24 accesses 0.
