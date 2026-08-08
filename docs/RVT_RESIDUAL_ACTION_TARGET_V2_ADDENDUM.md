# RVT Residual-Action Target V2 Addendum — Action-Pipeline Erratum

Schema: `rvt-residual-action-pipeline-erratum/v1`. Machine-readable form:
`results/rvt_fd24/residual_action_pipeline_erratum_v1.json`.

This is **additive**. `docs/RVT_RESIDUAL_ACTION_TARGET_V1.md` is not edited, and its
hash in `results/rvt_fd24/experiment_protocol_manifest.json` stays valid.

## The erratum

`RVT_RESIDUAL_ACTION_TARGET_V1.md:11` says "`u_base_i` is the frozen Phase 6
**projected** robot-local action". That wording is inconsistent with three
authoritative sources, and the owner decision is that the publication action
pipeline is authoritative.

| source | says |
|---|---|
| `FULLY_DECENTRALIZED_RVT_SYSTEM_MODEL.md:117-122` | `u_i(t) = f_safe(I_i(t), u_base_i(t) + delta_u_i(t))` |
| `robot_local_controller.py` | `base_action` is the plain pre-projection sum; `projected_action` is a separate output field |
| `phase9c_rb/session.py` | the command disturbance is added to `base_action` and the unchanged projection is then reapplied — the same insertion point a residual uses |
| `targets.py::DenseActionSample` | stores `base_action_world_acceleration` and `projected_base_action_world_acceleration` as two distinct fields |

## Authoritative names

```text
u_base_pre_safety       = frozen Phase 6 local base action, pre-projection
                          (formation + goal + damping + obstacle)
delta_u_world           = the residual candidate for robot i
u_candidate_pre_safety  = u_base_pre_safety + delta_u_world
u_safe_candidate        = local_safety_projection(u_candidate_pre_safety)
```

Units `m/s²`; frame **world**; control period `dt = 0.15 s`. The residual is
applied **before** the local safety projection.

## Candidate intervention duration

A residual candidate changes robot *i*'s local action for exactly **one** control
interval, `[t, t + dt)`, with `dt` the existing frozen control period. No holding
duration parameter is introduced, and the candidate residual is **not** reapplied
through the rollout. After that interval robot *i* resumes the normal frozen local
publication policy.

## Counterfactual evaluation duration

There is **no** new lookahead horizon, discount factor or planning horizon. After
the single-interval intervention the counterfactual continues under normal frozen
policies until the ordinary frozen termination: a task terminal state, or the
existing episode/family horizon.

So two durations must never be conflated:

| | duration |
|---|---|
| candidate intervention | 1 control interval |
| counterfactual evaluation | remainder of the existing frozen episode |

**No conflict with hashed Phase-8 semantics.**
`RVT_COUNTERFACTUAL_ROLLOUT_PROTOCOL.md` fixes the timeout as the family horizon
for *topology*-candidate rollouts and imposes no separate action-candidate
duration; `RVT_DENSE_ACTION_DATA_CONTRACT.md` constrains row content and density,
not evaluation duration. Nothing hashed is contradicted, so SPEC-5's stop
condition does not fire.
