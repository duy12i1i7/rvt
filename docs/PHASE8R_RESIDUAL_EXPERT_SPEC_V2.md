# Phase 8R — Pre-Data Residual Expert Specification Completion

> **Superseded in part by Phase 8R-V2B.** This document records the SPEC-1…SPEC-20
> audit that stopped at Verdict A. The owner has since frozen the four utility
> semantics, and the completed specification now exists as
> `results/rvt_fd24/residual_expert_spec_v2.json` (schema
> `rvt-residual-expert-spec/v2`). See
> [PHASE8R_RESIDUAL_EXPERT_UTILITY_V2B.md](docs/PHASE8R_RESIDUAL_EXPERT_UTILITY_V2B.md).
> Everything below remains accurate as the record of *why* those four decisions
> had to be made by the owner rather than derived.

**Result of this phase: the specification was not complete. Verdict A.**

Fifteen of the twenty owner decisions in this phase are now frozen and testable.
The one that decides whether RB-15 can be retried — SPEC-12, the utility
normalizers — does not resolve for **any** of the four utility components. Per
the owner rule, no number was chosen and the V2 expert was not implemented.

Machine-readable: `results/rvt_fd24/residual_expert_spec_v2_audit_v1.json`
(schema `rvt-residual-expert-spec-v2-audit/v1`). The completed specification
artifact `residual_expert_spec_v2.json` was deliberately **not** written in this
phase, because SPEC-19 conditioned it on SPEC-10 through SPEC-12 resolving.

## What is now frozen

### SPEC-1/2 — the candidate lattice

Nine candidates, `dx ∈ {−bx, 0, +bx} × dy ∈ {−by, 0, +by}`, in canonical
x-major order. `bx, by` are never written: they come from
`residual_action_limits(model_config, runtime_config) =
residual_limit_fractions_of_maximum_acceleration × a_max = (0.25, 0.25) × 0.6`.

| index | candidate (m/s²) | | index | candidate |
|---:|---|---|---:|---|
| 0 | (−0.15, −0.15) | | 5 | (0.00, +0.15) |
| 1 | (−0.15, 0.00) | | 6 | (+0.15, −0.15) |
| 2 | (−0.15, +0.15) | | 7 | (+0.15, 0.00) |
| 3 | (0.00, −0.15) | | 8 | (+0.15, +0.15) |
| 4 | **(0.00, 0.00)** | | | |

Zero residual occurs exactly once, at index 4. Candidate-set hash
`9cf6a473b2550ec484d7ce932c7024ca07bc71c9fdcea9ddb179b0faadfcb706`. Not
N-specific, not topology-specific, no configurable resolution, no random or
Gaussian sampling, no intermediate magnitude. Implemented in
[residual_lattice.py](rvt_swarm/phase8r/residual_lattice.py) — enumeration only:
it evaluates nothing, computes no utility, runs no rollout and never calls the
frozen selector.

### SPEC-3/4/5 — action pipeline, intervention, evaluation

See [RVT_RESIDUAL_ACTION_TARGET_V2_ADDENDUM.md](docs/RVT_RESIDUAL_ACTION_TARGET_V2_ADDENDUM.md).
The residual enters **before** the local safety projection; the intervention lasts
exactly one control interval; the counterfactual then runs under normal frozen
policies to ordinary termination. No hashed Phase-8 requirement is contradicted,
so SPEC-5's stop condition does not fire.

### SPEC-6/7 — information boundary

`ACTION_INFORMATION_LOCAL = true`, `LABEL_ORACLE_CENTRALIZED = true`, kept
strictly separate. `robot_local_information_only` certifies the provenance of the
information used to *construct the candidate action* and its local admissibility;
it makes no claim about the offline outcome oracle. A separate
`label_oracle_centralized` field is required and belongs to the V2 expert module,
not to the frozen V1 dataclass — nothing was added to V1 here.

SPEC-7's stop condition does **not** fire: the V1 field carries no docstring, and
the hashed contract says only that "non-local candidates are ineligible", which is
a statement about candidate construction. No explicitly frozen definition is being
redefined.

### SPEC-8/9 — feasibility and safety

`locally_feasible` is narrow: the candidate can be constructed and the one-interval
intervention executed inside the local controller/dynamics domain — finite view
fields, finite base action, finite residual, finite pre-safety candidate action,
valid input domain. It does **not** mean safety success, collision-free rollout,
task success or recoverability. It does not duplicate the selector's bound and
disk checks. `safety_projection_compatible` comes from the existing robot-local
own-action projection, with no global oracle and no altered constraints.

### SPEC-14/15/16 — execution and selector

Identical canonical snapshot per candidate, matched exogenous streams, no
candidate starting from another's terminal state; other robots run their ordinary
frozen local policies; the V1 selector is untouched — eligibility conjunction,
utility calculation, deviation semantics, deterministic tie-break and
no-eligible-candidate failure all preserved.

## SPEC-10 — the utility field audit

| field | weight | direction | raw quantity frozen? | normalizer unique? |
|---|---:|---|---|---|
| `normalized_progress` | +1.00 | higher better | no (plausibly `RobotView.local_progress`, m) | **yes** — `nominal_spacing_meters`, the only progress normalizer in the repository (`ego_graph_v2.local_progress_spacing`) |
| `normalized_clearance_margin` | +0.50 | higher better | **no** | **no** — five frozen metre-valued candidates |
| `normalized_formation_error` | −0.25 | lower better | yes, but as a **2-vector** | **no** — spacing (0.9) vs Metric V3 tolerance (0.55) |
| `normalized_action_deviation` | −0.05, and the secondary tie-break key | lower better | yes, but as a **2-vector** | normalizer yes; **norm choice no** |

## SPEC-12 — why all four fail

**`normalized_progress`.** The normalizer is unique. What is not defined is the
*temporal reduction*: SPEC-5 evaluates each candidate over the remainder of the
episode, so the term is an outcome statistic — and no frozen source says whether
progress is read instantaneously at the decision step, at the counterfactual
terminal state, or reduced over the trajectory (final, mean, min, integral). The
choice changes the sign structure of the whole utility.

**`normalized_clearance_margin`.** Neither the raw statistic nor the normalizer
exists. Minimum or mean? Over peers, obstacles, or both? Raw distance, or margin
above the required clearance? And the frozen scheme normalizes peer range by
`R_comm` and obstacle clearance by `R_obs` — two distinct fields that merely
happen to share the value 3.0 m today — while `parameters.py` normalizes a
clearance by `nominal_spacing` and the derived config offers
`robot_obstacle_required_clearance = 0.55` and
`robot_robot_required_clearance = 0.40`. Five citable frozen quantities, no rule.

**`normalized_formation_error`.** The frozen Phase-6 quantity is a *2-vector*
(`mean(actual − desired offset)`), and the utility term is a scalar; the reduction
is not frozen. The normalizer is also contested: `nominal_spacing` has two
independent frozen precedents as a normalizer (the Phase-6 formation term and
`ego_graph_v2.formation_residual_spacing`), while Metric V3's `epsilon_form =
0.55 m` is the frozen scale at which formation error becomes significant — a
factor of 1.636 apart.

**`normalized_action_deviation`.** The normalizer is the frozen residual bound,
but the *scalarizing norm* is not frozen, and on this exact lattice the choice is
material rather than cosmetic:

| norm | zero | edge | corner | separates edge from corner? |
|---|---:|---:|---:|---|
| L∞ over the componentwise bound (the selector's own admissibility norm) | 0 | 1.0000 | 1.0000 | **no** |
| L2 over the Euclidean bound norm | 0 | 0.7071 | 1.0000 | yes |
| L2 over `b_x` (the Phase-8 diagnostic fixture rule) | 0 | 1.0000 | 1.4142 | yes |

Under L∞ all eight non-zero candidates tie on deviation, so the frozen secondary
tie-break key becomes inert and the third key decides. Under L2 the four edges are
preferred over the four corners. The three rules select **different expert
actions**, so this is not bookkeeping.

## SPEC-13 — not reached

Classification into `LOCAL_ACTION_INFORMATION` / `OFFLINE_LABEL_ORACLE` /
`DERIVED_FROM_BOTH` is conditional on SPEC-10/12 and would be premature: whether a
term is local or oracle-side depends entirely on whether it is read at the
decision step or from the counterfactual outcome, which is exactly what is
undefined.

## SPEC-17 — generation-budget impact

**Record caps survive.** A dense row is one `(episode, timestep, robot, topology)`
row carrying the *selected* expert action, not one row per candidate, so a 9-point
lattice does not multiply any stored record count. The 536,000 total, the 332,900
recoverability rows and the 42,840 candidate replica rollouts (which count
*topology* candidates, not action candidates) all remain valid upper bounds, and
none was changed.

**Two frozen fields are invalidated.**

1. `timeout_contract.wall_clock_seconds.residual_action_cell_generation_job = 1800 s`.
   A train residual cell now needs 2000 × 9 = 18,000 full counterfactual
   continuations, i.e. 100 ms each. A complete publication episode measured
   ≈ 2.0 s in the v6 sweep (450 executions in 886 s); even at a half-episode
   average the requirement exceeds the stored budget by roughly an order of
   magnitude. Since `wall_clock_timeout_classification` is
   `infrastructure_generation_failure`, every residual cell would be classified as
   an infrastructure failure.
2. `job_identity_contract.residual_cell = [study, split, family, layout_sha256,
   team_size]` carries no candidate or row dimension, so the nine evaluations
   behind one dense row have no identity, cannot be retried individually, and
   cannot be audited under `duplicate_semantic_identity_policy = "reject"`.

An **additive** proposal is recorded in
`results/rvt_fd24/proposed_generation_budget_addendum_v2.json`. It proposes no
numbers: the timeout value is an owner decision. Neither the existing budget nor
the job manifest was modified.

## SPEC-18 — RB-16

Synthetic residual rotation augmentation is **disabled**. No predeclared
non-identity equivariant transform set exists: the loss contract defers the
consistency term to "a later enabled variant [that] may compare only predeclared
local equivariant transforms", and no such set is declared anywhere. If an
authoritative frozen transform set is later found it must be reported before this
decision changes. When RB-15 eventually passes, RB-16 primary behaviour is limited
to native world-frame verification, identity-transform equivalence, and explicit
confirmation that no synthetic rotation labels are emitted.

## SPEC-20 — protocol versioning

The Phase-8 composite hash is **not** the complete residual label contract. A
future residual provenance record must reference the historical V1 contract, this
phase's erratum, the RB-15 findings, the field mapping, and — once written — the
completed V2 specification. RB-17 execution manifests must reference that
composite, not the Phase-8 composite alone. Nothing was mutated in this phase.

## What is required before RB-15 can be retried

One owner decision, in four parts, each frozen as a hashed quantity:

1. the temporal reduction of the state-derived utility terms over the
   counterfactual;
2. the raw clearance statistic and its normalizer;
3. the formation-error scalar reduction and its normalizer;
4. the deviation scalarizing norm.

## Scope counters

Recoverability rows 0. Residual supervision rows 0. Scientific shards 0. New
checkpoints 0. Optimizer states 0. No canary requiring V2 labels. RB-15 not
retried, RB-16 not begun, no training. Historical Phase-8 artifacts unchanged.
