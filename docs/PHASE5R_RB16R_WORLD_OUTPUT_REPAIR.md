# Phase 5R / RB16R — Residual Model Output-Frame Repair and Requalification

**Result: the WORLD frame is now authoritative end to end. Verdict C.**

RB-16 stopped because the residual path had two frames. The owner froze the
repair direction — `PRIMARY_RESIDUAL_OUTPUT_FRAME = WORLD` — and this phase
implements it, proves the representation question it raises, and requalifies
RB-16.

| artifact | hash |
|---|---|
| model residual output-frame erratum | `3786f9925a8373abb384955d6e34fa781caf9616d04e1f8cdce69ca0c9f1e6b8` |
| RB-16 requalification | `10c4aebe41a98db7674f7ee617db8a209a148bdfe18ca76bd04cde59660ab387` |
| current residual-runtime composite | `24c65a41855a2ffe9345755f0630dfe707e9446065d7cef8516f8f1e89cb19ff` |
| RB-16 frame-conflict audit (**preserved, unmodified**) | `de697d1253081b907afc3e3e5e275527c0c0f80ac873b140d84e30737478963c` |

## Why WORLD

The already-qualified chain — expert candidate and evaluation → target builder →
dense target → runtime base-action addition → local safety projection — is
world-frame at every step. The model output declaration was the single
conflicting element. And rotating a *componentwise* box changes its admissible
set: the corner `(0.15, 0.15)` read in the other frame becomes `(0.1450, 0.1548)`,
outside the frozen bound. So the repair moves the model declaration and rotates
nothing.

## The head never rotated anything

`FD24ResidualActionHead` was `Linear → ReLU → Linear`, with `tanh × limits`
applied by the parent. No `cos`, `sin`, basis change or heading term existed in
the forward path. The historical mission naming corresponded to no arithmetic:
`OLD_MISSION_OUTPUT_DECLARATION_IS_METADATA_ONLY = true`.

## Representation identifiability — CASE II, proven

Under a rigid **37°** rotation of the whole scene, built through the authoritative
ego-graph pipeline:

| quantity | result |
|---|---|
| node feature tensor | **bit-identical**, max abs difference `0.0` |
| edge feature tensor | **bit-identical**, max abs difference `0.0` |
| diverging feature blocks | **none** |
| required WORLD target | `(0.075, −0.0375)` → `(0.0825, 0.0152)`, differing by `0.0527` m/s² |

Every ego-graph vector feature is mission-frame by construction (`_to_mission`),
and no feature encodes the absolute mission→world orientation. So the WORLD
output was **not a single-valued function of the model input** — renaming the
components would have been a lie. CASE II therefore required the minimal frame
context of R16R-6.

## The minimal frame context

`(cos θ, sin θ)` of the mission-to-world orientation, taken from
`RobotView.mission_dir` through **the same** `_mission_axes` transform the
ego-graph builder already applies to every feature — its longitudinal axis *is*
`(cos θ, sin θ)`. No separately calculated heading exists.

It is carried as `RobotLocalEgoGraph.mission_orientation_cos_sin`, a
**record-level** field: no node or edge feature was added, `NODE_FEATURE_DIM`
(35), `EDGE_FEATURE_DIM` (19) and the ego feature schema hash are unchanged, and
graph topology, message passing and global-pooling status are untouched. Only
`FD24ResidualActionHead` consumes it; the encoder, candidate conditioner and
recoverability head do not.

**Decentralization.** Moving a hidden non-neighbour robot leaves the orientation
and every ego feature bit-identical; all robots in a team read one identical
orientation; no leader, no team-global estimator, no online aggregation. It is
declared to the strict-decentralization guard through that guard's own
local-tensor allowlist, and the guard's full audit is clean.

**Non-vacuity.** With only the ego features the rotated pair is indistinguishable.
With the orientation restored the model inputs differ by exactly that field, the
residual outputs differ — and the recoverability logits remain equal, confirming
the context reaches only the residual head.

## Model V2

| | V1 (historical, preserved) | V2 (current) |
|---|---|---|
| schema | `rvt-fd24-model/v1` | `rvt-fd24-model/v2` |
| input / output schema | `…-input/v1`, `…-output/v1` | `…-input/v2`, `…-output/v2` |
| components | `mission_longitudinal_acceleration`, `mission_lateral_acceleration` | `world_x_acceleration`, `world_y_acceleration` |
| declared output frame | MISSION | **WORLD** |
| input frame | MISSION | MISSION (unchanged) |

Nothing claims V1 ever said WORLD. The mixed-frame contract is explicit: the
encoder consumes mission-frame local observations and the residual head
additionally consumes the orientation, so a WORLD output is well defined. **No
rotation-equivariance claim is made.**

Parameters: residual head `9,506 → 9,698` (+192 = 2 × 96, the first `Linear`
widened by the two context inputs). Encoder, candidate conditioner and
recoverability head unchanged; total `272,227`.

## Bounds and saturation

`residual_action_limits` remains the single source: expert eligibility, target
clip, model head clamp and runtime all read `(0.15, 0.15)` **as WORLD-axis
limits**. No rotated box, no mission-frame box, no enlarged `0.154…` bound, no
post-rotation clipping — there is no residual rotation to clip after.

`tanh` is `< 1` for every finite logit, so a target exactly on a component
boundary is a limit point the head approaches but cannot attain. **8 of the 9**
lattice candidates sit on a boundary. Smooth L1 is well defined there and no loss
requires exact equality, so this is documented as a model parameterization
limitation and the frozen expert is unchanged.

## Unchanged by construction

Residual Expert V2 spec `e3a30930…`, label composite `8921424d…`, RB-15 binding
`9edc8cc8…`, the 9-point lattice, the utilities, the target builder, the target
frame and the target bounds — all verified untouched in test.

## Scope guards were narrowed, not disabled

The repair changes five files that frozen-file guards protect. Each guard now
allows exactly the RB16R-authorized set and still fails on any other frozen file.
The frozen Phase-8 experiment-protocol manifest is **not** rewritten: the
preflight model-schema check admits the new version only because the erratum
artifact records the supersession, so the allowance is data, not a hardcoded
string.

## Isolation

Recoverability rows 0, residual rows 0, shards 0, FD24 checkpoints 0, optimizer
states 0, training operations 0, final-test accesses 0, Study A N=24 accesses 0.
`PRIMARY_SYNTHETIC_ROTATION_AUGMENTATION` stays **DISABLED**, transform
multiplier 1, transformed rows 0 — the rotated-state test is diagnostic only.
