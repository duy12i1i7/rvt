# Phase 9C-RB16 — Native Action-Frame Binding and Identity-Transform Verification

**Result: the primary residual path does not have one frame. Verdict B.**

The world segment is clean and verified exactly. The blocking finding is at the
model boundary: the FD24 residual head's two output components are declared in
the **mission** frame, while the expert target, the training-row schema and the
runtime insertion are all **world** frame — and the mission frame is never the
world frame in any publication layout.

Machine-readable: `results/rvt_fd24/rb16_native_action_frame_v1.json`
(`de697d1253081b907afc3e3e5e275527c0c0f80ac873b140d84e30737478963c`).

## The six statements RB16-20 asks for

1. **Primary residual labels are WORLD-frame acceleration vectors.** Verified:
   `ResidualActionTarget.residual_target_world_acceleration` and
   `DenseActionSample.residual_target_world_acceleration`, shape `[2]`, units
   m/s², and the dense-action contract states "World-frame acceleration and
   `dt=0.15 s` are explicit."
2. **Primary model outputs are interpreted in the same WORLD frame — NOT
   ESTABLISHED.** This is the blocking conflict. See below.
3. **The learned residual is added to the WORLD-frame pre-safety base action.**
   Verified: `local_safety_projection(base_action + delta)` with `base_action`
   the world-frame Phase-6 sum.
4. **Synthetic non-identity rotation augmentation is disabled.** Verified: no
   random angle, no quarter-turn, no reflection, no label duplication, no
   equivariance consistency loss, 0 transformed rows.
5. **No rotation-equivariance claim is made for the primary study.**
6. **RB16 generated no scientific supervision.** 0 rows, 0 shards, 0
   checkpoints, 0 optimizer states, 0 training operations.

## The conflict

| side | components | evidence |
|---|---|---|
| **WORLD** | expert target, dense row, Phase-6 `base_action`, runtime insertion, RB-15 V2 producer | field names state the frame; the residual is added componentwise to the world-frame base action |
| **MISSION** | `RVTLocalBatchOutput.residual_action`; every `ego_graph_v2` feature the model consumes | `ROBOT_LOCAL_ACTION_COMPONENTS = ("mission_longitudinal_acceleration", "mission_lateral_acceleration")` — the sole declaration of what the two outputs mean; features are rotated by `_to_mission` |

The two frames are **not** the same. All 30 publication layouts have a mission
longitudinal axis rotated **1.817°–1.909°** from world +x, and **none** is
world-aligned.

The consequence is material, not cosmetic. The componentwise residual bound is a
*box*, and a box is not rotation invariant: the corner residual `(0.15, 0.15)`
read in the other frame becomes `(0.1450, 0.1548)` — **outside** the frozen
0.15 bound that the selector's eligibility conjunction and the target builder's
clip both depend on. An axis-aligned `(0.15, 0)` acquires a cross-axis component
of 0.0049 m/s².

RB16-6's escape hatch — pin an unnamed model frame to WORLD from the consumer
path — does not apply, because the frame *is* named, and it is named mission.
RB16-1 forbids inserting a conversion to make the audit pass. So RB16 records the
conflict and stops.

**No conversion was inserted.** No world↔mission conversion for *actions* exists
anywhere in the repository: `rotate_template_vector` and `roles.rotation` convert
role/template geometry into world, and `ego_graph_v2._to_mission` converts
observations, never an action.

## What the owner must decide

Either **WORLD** — then `ROBOT_LOCAL_ACTION_COMPONENTS` must be renamed or
superseded additively, and it must be stated that the head emits world-frame
components from mission-frame features (legitimate, but it needs saying) — or
**MISSION** — then an authoritative mission→world conversion must be frozen for
the residual, applied on exactly one side, and the componentwise bound
re-examined because a box is not rotation invariant.

RB-16 does not choose.

## What is verified exactly

**Identity transform.** `T_identity(delta_u_world) = delta_u_world`. No general
rotation API was created. Four cases run target builder → row encode → row decode
→ injected deterministic model output → runtime pre-safety addition, and all four
arrive **bit-identical**, including a deliberately non-symmetric test-only vector
`(0.075, −0.0375)` where `|dx| ≠ |dy|` and the signs differ — the case an axis
swap or quarter-turn could not survive. No swap, no sign inversion, no scale
change, no rotation. That vector exists for frame plumbing only and is **not** a
candidate.

**Bound equality.** Expert eligibility, target clip, model head clamp and runtime
all read the same `residual_action_limits(model_config, runtime_config)` —
`(0.15, 0.15)` — with no independent literal.

One property is recorded rather than corrected: the head emits
`tanh(raw) × limits`, so a target exactly at a componentwise bound is a limit
point it approaches but never emits. Strictly interior targets round-trip within
float32 (3.0 × 10⁻⁹ on the test vector). The bound itself is unchanged.

## Counts and semantics unchanged

`PRIMARY_TRANSFORM_MULTIPLIER = 1`. Candidate count still 9; candidate-evaluation
upper bound still 4,824,000; stored dense row cap still 536,000. RB-16 added no
candidate evaluations and no rows.

The RB-15 no-eligible finding is preserved: a decision state may have **zero**
eligible residual candidates when all nine fail the frozen eligibility
conjunction — observed once in the RB-15 canary. No zero, rotated or clipped
fallback was added, and RB-17 must preserve the exact outcome and never fabricate
a residual target.

## Session provenance

RB-15 refactored `session.py` behaviour-identically, so the file hash the frozen
V2 spec cites (`ad105e91…`) no longer matches the current file (`9a88932f…`).
This artifact records both, the semantic quantity actually cited — the
robot-robot minimum admissible clearance, unchanged and re-derived in test — the
equivalence evidence, and the RB-15 binding hash. The V2 spec was **not**
rewritten, and nothing claims the historical hash matches the current file.
