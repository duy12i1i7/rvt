# Phase 9C-RB15 — Frozen Residual Expert Candidate-Evaluation Binding

**Result: the binding cannot be implemented as specified. Verdict A.**

The frozen residual expert `B_FROZEN_COUNTERFACTUAL_LOCAL_ACTION_SEARCH_V1` has a
frozen *selector*, a frozen *residual bound* and a frozen *target builder*. It has
**no frozen candidate enumeration, no frozen score normalizers, no frozen
candidate rollout horizon, and no frozen definition of two of its own eligibility
fields.** Producing any of them here would mean inventing supervision semantics,
which RB15-1, RB15-13 and RB15-14 explicitly forbid.

This document is the RB15-0 read-out plus the RB15-1 audit. No production
candidate enumerator was written.

## Headroom provenance (RB15-25)

| artifact | hash |
|---|---|
| headroom v6 | `d044d6b99d7a2bbb83565b121d188a35e335bfd856e3eb0e885823ca1a6742ef` |
| detached reproduction | `1f08ba77315e6fdbabfeac8f9350e6f5cd64468c431ecc9fba19747fcd26af32` |
| authority record | `fafe1460c69ef37ca9134c2fc17721adddda92607e3e4e3c084d6a29d9dab509` |

`H2_PRE_DATA_VIABILITY = true`. `H2_EMPIRICALLY_CONFIRMED = false`.

The additive F5 interpretation is preserved unchanged: `train/train-f5-00/N8`,
category `RECONFIGURATION_REQUIRED`, completed switching epochs `0`, mechanism
`PARTIAL_ATTEMPT_EFFECT`. It is not a completed topology switch and must not be
cited as one.

## RB15-0 — what the frozen expert actually is

Authoritative sources read in full: `rvt_swarm/phase8/targets.py`,
`rvt_swarm/phase8/diagnostic.py`, `tests/test_residual_action_target.py`,
`rvt_swarm/fd24/configuration.py`, `rvt_swarm/fd24/model.py`,
`rvt_swarm/phase9c/artifacts.py`, `docs/RVT_RESIDUAL_ACTION_TARGET_V1.md`
(hashed protocol document, hash verified unchanged),
`docs/RVT_COUNTERFACTUAL_ROLLOUT_PROTOCOL.md`,
`docs/RVT_DENSE_ACTION_DATA_CONTRACT.md`,
`docs/RVT_TASK_RECOVERABILITY_TARGET_V4.md`, `docs/RVT_FD24_LOSS_CONTRACT.md`,
`docs/RVT_FD24_METRIC_CONTRACT.md`, `docs/PHASE8_EXPERIMENT_PROTOCOL_REPORT.md`,
`docs/PHASE8_TARGET_NON_VACUITY_DIAGNOSTIC.md`,
`docs/PHASE9_RESIDUAL_EXPERT_LOCALITY_AUDIT.md`,
`docs/FULLY_DECENTRALIZED_RVT_SYSTEM_MODEL.md`,
`results/rvt_fd24/experiment_protocol_manifest.json`,
`results/rvt_fd24/datasets/phase9_residual_audit.json`, and `latex/access.tex`.

### Selector — frozen, complete

`select_counterfactual_local_action(base_action, evaluations, runtime_config,
model_config)` at [targets.py:323](rvt_swarm/phase8/targets.py:323).

Eligibility, all five required simultaneously:

1. `item.locally_feasible`
2. `item.safety_projection_compatible`
3. `item.robot_local_information_only`
4. componentwise `|action[k] - base[k]| <= limits[k] + 1e-12`
5. `hypot(action) <= a_max + 1e-12`

Selection is `max` over the lexicographic key
`(utility(), -normalized_action_deviation, action_world_acceleration)`.
`utility() = progress + 0.50*clearance_margin - 0.25*formation_error -
0.05*action_deviation` — weights frozen in code and restated in
`RVT_RESIDUAL_ACTION_TARGET_V1.md`.

If no candidate is eligible the frozen behaviour is
`raise ValueError("local action search has no eligible robot-local candidate")`.
There is no fallback and no no-op default (RB15-17).

### Candidate and evaluation representation — frozen

`LocalActionEvaluation` ([targets.py:239](rvt_swarm/phase8/targets.py:239)) is a
frozen 8-field dataclass: `action_world_acceleration` (2-vector),
`locally_feasible`, `safety_projection_compatible`,
`robot_local_information_only`, `normalized_progress`,
`normalized_clearance_margin`, `normalized_formation_error`,
`normalized_action_deviation`.

### Residual target — frozen

`build_residual_action_target` at [targets.py:360](rvt_swarm/phase8/targets.py:360)
computes `clip(u_expert - u_base, +/- limits)` componentwise and reports
`finite`, `nonzero` (`hypot > 1e-12`), `saturated` (`|component| >= limit -
1e-12`) and the expert's `safety_projection_compatible`.

### Frame, units, bound — frozen and derived

World-frame acceleration, m/s^2, at `dt = 0.15 s`. The bound is *derived*, never a
literal: `residual_action_limits(model_config, runtime_config) =
residual_limit_fractions_of_maximum_acceleration * a_max = (0.25, 0.25) * 0.6 =
(0.15, 0.15) m/s^2`, plus the physical disk `hypot(u) <= 0.6`. RB15-2 is therefore
satisfiable without introducing any new constant — and no new constant was
introduced, because no enumerator was written.

### `robot_local_information_only` — frozen meaning

The field is per **candidate evaluation**, and the frozen selector uses it purely
as an eligibility filter: a candidate carrying non-local information is dropped,
not penalised (`tests/test_residual_action_target.py:52`). The hashed contract
says the expert "uses exactly the sampled robot's permitted local information and
the same local safety compatibility check ... It is not a centralized joint-action
expert", and the rollout protocol says "The candidate receives no privileged
future state. The offline evaluator may inspect complete outcomes after rollout,
but saved model inputs remain robot-local."

Read together, the frozen semantics separate exactly as RB15-6 anticipates:
`ACTION_INFORMATION_LOCAL` must be true, while a centralized offline outcome
oracle is permitted for *labels*. What the frozen text does **not** say is whether
the four normalized utility terms are label-side (oracle-scored) or
action-side (locally computed) quantities. Because they feed `utility()`, which
selects the action, the only conservative reading is action-side — and under that
reading they must be computable from `RobotLocalView`, which no frozen source
defines how to do.

## RB15-1 — candidate enumeration authority: **absent**

The two known producers were compared exactly.

| dimension | `phase8/diagnostic.py::_action_evaluations` | `tests/test_residual_action_target.py` |
|---|---|---|
| candidate count | 3 | 3 |
| base action | `(0.10 + 0.005*(i mod 3), 0.02*((i mod 2)*2 - 1))` | `(0.1, 0.0)` |
| candidate 2 delta | 4-cycle on `i mod 4`: `(0,0)`, `(0.05,-0.03)`, `(-0.04,0.06)`, `(0.15,0)` | `(0.1,-0.05)` |
| candidate 3 | `(base_x, base_y + 0.01)`, non-local decoy | `(0.11, 0.0)`, non-local decoy |
| zero residual | candidate 1 always; candidate 2 **collapses onto it** when `i mod 4 == 0` (duplicate candidates) | candidate 1 only |
| progress / clearance / formation | literals `0.40/0.35/0.30` and `0.65/0.50/0.20` | literals `0.2/0.4/0.2` and `0.8/0.4/0.2` |
| action deviation | computed `hypot(delta)/limit` | literal `0.2` for all three |
| ordering | `(baseline, expert, rejected_global)` | `(base, improved, non-local)` |
| topology-conditioned | no | no |
| N-conditioned | no (`RuntimeConfig.for_team_size(5)` fixed) | no |

**They disagree** on base action, candidate values, score values and the deviation
rule — RB15-1's first stop condition.

**And neither is frozen.** `phase8/diagnostic.py` is documented in its own module
docstring as a "Predeclared tiny target non-vacuity diagnostic; never a scientific
dataset"; `PHASE8_TARGET_NON_VACUITY_DIAGNOSTIC.md` calls its outputs "16
robot-local residual-target **fixtures**". It is not among the twelve hashed
protocol documents in `experiment_protocol_manifest.json` (the only hashed `.py`
there is `phase8/final_test_guard.py`). Its candidate deltas are keyed on a loop
counter `sample_index`, and it produces duplicate identical candidates on one
quarter of its samples — behaviour that is unproblematic for a non-vacuity fixture
and disqualifying for a scientific enumeration. That is RB15-1's second stop
condition.

The only mention of an enumeration anywhere in the repository is one permissive
clause in the hashed contract: the expert "**may** evaluate a fixed offline
candidate lattice" (`RVT_RESIDUAL_ACTION_TARGET_V1.md:8`). No count, no
resolution, no radius, no ordering, no zero-inclusion rule, no
topology/N-conditioning is stated anywhere. Choosing any of them here would be
precisely the forbidden new candidate-search hyperparameter.

## Three further specification gaps found

### 1. The utility normalizers do not exist

`utility()` consumes `normalized_progress`, `normalized_clearance_margin`,
`normalized_formation_error` and `normalized_action_deviation`. A
repository-wide search finds **no code that computes any of them** — the only two
constructors of `LocalActionEvaluation` supply literals. The contract says "All
terms use frozen local SI normalizers"; those normalizers are not defined in any
code path, any hashed protocol document, or the manuscript. Three of the four
have no indicated rule at all; `normalized_action_deviation` has one *fixture*
rule (`hypot(delta)/residual_limit`) that the unit test contradicts.

Without normalizers the frozen weights `0.50 / -0.25 / -0.05` are not a defined
objective, so RB15-14's "use the frozen objective exactly" cannot be honoured.

### 2. No candidate rollout horizon exists (RB15-13)

`horizon_seconds` in `CounterfactualRolloutTrace` belongs to the **topology**
candidate rollouts (COMPACT vs LINE) and is "the family horizon"
(`RVT_COUNTERFACTUAL_ROLLOUT_PROTOCOL.md`). The residual expert performs no
rollout at all in any existing producer: its scores are literals. No frozen source
gives a per-action-candidate horizon, step count, discount or lookahead. This is
RB15-13's stop condition verbatim — a supervision-definition ambiguity.

### 3. `locally_feasible` has no frozen definition

Both producers set it to a literal `True`. Nothing defines what local feasibility
means as distinct from `safety_projection_compatible`.

## RB15-10 — action pipeline boundary: an internal contradiction

The frozen system model is explicit
(`FULLY_DECENTRALIZED_RVT_SYSTEM_MODEL.md:117-122`):

```text
u_base_i(t)  = f_base(I_i(t), commit_i(t))
delta_u_i(t) = f_residual(I_i(t), commit_i(t); theta)
u_i(t)       = f_safe(I_i(t), u_base_i(t) + delta_u_i(t))
```

The residual is added **before** the local safety projection — boundary **A**. The
publication runtime matches exactly: `output.base_action` is the pre-projection
Phase 6 sum and disturbances are added to it *before* the unchanged projection is
reapplied ([session.py:474](rvt_swarm/phase9c_rb/session.py:474)). `DenseActionSample`
stores `base_action_world_acceleration` and
`projected_base_action_world_acceleration` as two distinct fields, which is only
meaningful if base is pre-projection.

Against all of that, the hashed action-target contract says "`u_base_i` is the
frozen Phase 6 **projected** robot-local action"
(`RVT_RESIDUAL_ACTION_TARGET_V1.md:11`). If taken literally the residual would be
added after projection, which contradicts the system model, the runtime and its
own dense-row schema.

The weight of evidence is clearly boundary A, but the authoritative hashed
document says otherwise, so RB15-10 forbids silently adapting either side. This is
recorded, not resolved.

## What *is* ready

These RB15 requirements are already satisfiable and were verified as present; they
are simply unexercisable without candidates.

- **RB15-7 snapshot source** — `phase9c_rb/counterfactual.py`: `snapshot`,
  `EpisodeSnapshot`, `clone_pair`, `canonical_execution_state`,
  `canonical_execution_hash`. Every candidate can restore the identical canonical
  snapshot; no approximate clone is needed.
- **RB15-8 matched streams** — the counter-keyed PRF in `phase9c_rb/streams.py`
  plus `replica_count_for_family` give matched disturbance, communication and
  dynamic-obstacle realizations with a canonical identity per evaluation.
- **RB15-11 base action** — `output.base_action` from the real frozen Phase 6
  controller at the snapshot; no reconstruction needed.
- **RB15-12 safety** — the existing local own-action projection
  (`controller.safety_projection.project`) can produce
  `safety_projection_compatible` per candidate without any global layer.
- **RB15-2 residual bound** — derived from config, no literal required.
- **RB15-16 target construction** — the frozen builder is directly callable.

The missing pieces are all *specification*, not *plumbing*.

## What is required before RB-15 can be retried

An owner decision freezing, as a hashed protocol document:

1. the exact candidate enumeration — count, values or generating rule, ordering,
   whether the zero residual is a member, and any topology/N conditioning;
2. the four normalizers, in SI, computable from `RobotLocalView`;
3. the definition of `locally_feasible`;
4. the per-candidate evaluation horizon, or an explicit statement that candidate
   scoring is instantaneous and therefore needs none;
5. whether the utility terms are action-side or label-oracle-side;
6. whether `u_base` is pre- or post-projection, correcting whichever document is
   wrong.

Until then any RB-15 implementation would be inventing the supervision it claims
to bind.

## Scope counters for this phase

Scientific supervision rows 0. Recoverability rows 0. Residual rows 0. Shards 0.
Checkpoints 0. Optimizer states 0. Expert calls in a scientific context 0.
Final-test accesses 0. Study A N=24 accesses 0. Expert code, objective, bounds,
controller, projection and locality boundary all unmodified.
