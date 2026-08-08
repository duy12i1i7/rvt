# Phase 8R-V2B — Utility Objective Freeze and Final Specification

**Result: Residual Expert V2 is scientifically complete pre-data. Verdict C.**

The owner froze the four utility semantics that Phase 8R could not derive. Both
hard-stop audits this phase demanded were run and both cleared, so the completed
specification now exists:

| artifact | hash |
|---|---|
| `results/rvt_fd24/residual_expert_spec_v2.json` | `e3a3093038b31f7f8c11d56be224929c9eccc27e6bde2fa47c5c6c644b7f3fbf` |
| `results/rvt_fd24/residual_label_contract_composite_v2.json` | `8921424d0342e26a7a22da4ca042543a8eb08c2dc310f5f5639b70678ceb08ad` |

Expert ID `B_FROZEN_COUNTERFACTUAL_LOCAL_ACTION_SEARCH_V2`. V2 completes producer
semantics **around** the V1 selector; the V1 selector, its weights, its tie-break
and the `LocalActionEvaluation` dataclass are byte-identical and hash-pinned.

## The four utility fields

### `normalized_progress` — weight +1.00, `OFFLINE_LABEL_ORACLE`

Raw source `RobotView.local_progress` (metres), the longitudinal progress of the
fitted topology origin along the mission direction, assigned by the frozen
`_update_progress`. Reduction is the **signed mean per-control-interval
increment**:

```text
normalized_progress = (1/K) * sum_{k=0}^{K-1} (p_{k+1} - p_k) / nominal_spacing_meters
```

No clipping, no absolute value, no maximum, no terminal total without the `1/K`.
Normalizer `nominal_spacing_meters`, the scale already linked to this quantity by
the frozen `ego_graph_v2.local_progress_spacing` feature.

**K = 0 audit — cleared.** Structurally, a dense row exists only where the
controller produced an action, and the frozen `step()` returns immediately once an
episode has terminated, so no row can sit at or after termination. Executably: 503
controller-run instants across three episodes — including one ending in
`COLLISION` — were snapshotted, restored and stepped. **Zero K = 0 cases.** The
reducer raises rather than defaulting if it ever sees one; no epsilon and no
fallback denominator exists.

### `normalized_clearance_margin` — weight +0.50, `OFFLINE_LABEL_ORACLE`

Worst signed physical safety slack over the counterfactual, normalized
constraint-by-constraint by that constraint's own frozen minimum admissible
clearance:

```text
slack_c(t) = (distance_c(t) - threshold_c) / threshold_c
normalized_clearance_margin = min_t min_c slack_c(t)
```

Positive is above the frozen threshold, zero is exactly at it, negative is a
violation. Nothing is clipped. Every threshold is the one the frozen **collision
truth** itself uses:

| constraint | distance | threshold | value |
|---|---|---|---|
| robot–robot | swept min centre distance | `derived.robot_robot_required_clearance_meters` | 0.40 m |
| robot–static circle | centre distance | `robot_radius + max(obstacle_clearance_margin, circle_radius)` | per obstacle |
| robot–corridor wall | `surface_distance` to wall material | `robot_radius + obstacle_surface_margin` | 0.20 m |
| robot–dynamic circle | swept min centre distance | `robot_radius + max(obstacle_clearance_margin, obstacle_radius)` | per obstacle |

Communication radius, sensing radius, nominal spacing and the Metric V3 tolerance
are **not** used — none of them is the authoritative safety constraint for any
physical relation. World-boundary exit is deliberately excluded: the owner
definition names exactly two constraint classes, and boundary exit remains a
separate frozen termination condition. `collision_tolerance_meters` (1e-9) is a
numerical guard inside the predicate, not part of the admissible clearance.

**Empty-set audit — cleared.** The smallest qualified team size is 5, so at least
ten robot–robot pairs are always applicable regardless of geometry. The set can
never be empty, and the reducer raises rather than inventing `+inf`, `1.0`, a
sensing-radius fallback or a synthetic distant obstacle.

### `normalized_formation_error` — weight −0.25, `OFFLINE_LABEL_ORACLE`

Raw source is the per-robot formation-error 2-vector — the Phase-6 mean pairwise
residual over fresh nominal neighbours. Scalarized by the **Euclidean norm**, not
L1, L∞ or a single axis. Reduced over time by **RMS**:

```text
normalized_formation_error = sqrt((1/M) * sum_t ||e_form(t)||^2) / nominal_spacing_meters
```

**M follows the frozen runtime's own trace convention.** Every per-step statistic
in `SimulatorEpisodeSession.step` — collision truth, progress, Metric V3 dwell,
deadlock window, goal dwell — is evaluated *after* the integration. The samples
are therefore the post-step states, the pre-step snapshot state is **excluded**,
and `M = K`. No extra endpoint sample is invented.

Normalizer `nominal_spacing_meters`, the frozen geometric scale of the formation.
Metric V3's `epsilon_form = 0.55 m` is explicitly **rejected**: it is an
acceptance/tube tolerance, not a geometric scale.

### `normalized_action_deviation` — weight −0.05 and the tie-break key, `LOCAL_ACTION_INFORMATION`

```text
normalized_action_deviation = ||delta_u_world||_2 / ||(bx, by)||_2
```

Euclidean in both numerator and denominator; not L∞, not normalized by `b_x`
alone. Fully known at candidate construction time — it needs no rollout and no
global information. On the frozen lattice the values **emerge from the formula**:
zero `0`, axis-edge `1/√2 ≈ 0.7071`, corner `1`. No `sqrt(2)` is written anywhere;
the reducer module's only numeric constants are `{0, 1, 2}`.

## Candidate lattice and tie-break

Nine candidates, hash
`9cf6a473b2550ec484d7ce932c7024ca07bc71c9fdcea9ddb179b0faadfcb706`, zero exactly
once at index 4. Tie-break `(utility(), −normalized_action_deviation,
action_world_acceleration)` is unchanged and now **non-vacuous**: with the
Euclidean deviation, an axis-edge candidate and a corner candidate that tie on
primary utility are separated by the secondary key, and the edge wins even though
the corner has the lexicographically larger action tuple. Enumeration order does
not determine the winner, forward or reversed.

## Execution semantics

One canonical `EpisodeSnapshot` per candidate, matched exogenous streams,
one-control-interval intervention, then normal frozen policies to ordinary
termination. All rollout-derived utility comes from that **single** trace — no
separate utility-specific simulation. Other robots run their ordinary frozen local
policies. Trajectories ending in collision, task failure, readiness failure or
horizon termination are **scored, not discarded**; only execution-invalid
candidates follow the frozen validity semantics.

## The reducers are not the producer

`rvt_swarm/phase8r/utility_v2.py` contains four pure reducers over an already
executed trace. It never snapshots, rolls out, enumerates candidates or calls the
selector — AST-pinned. Every normalizer is read from the authoritative
configuration inside the function, so a caller cannot substitute a scale, and no
normalizer constant appears in the file. The identifier allowlist makes a
dataset-, batch-, percentile- or fit-dependent normalization unspellable.

## Budget and RB-16

Stored dense-row cap **536,000**, unchanged. Candidate evaluations per row **9**.
Candidate-evaluation upper bound **4,824,000** — a **compute** bound, not a stored
row count. `RESIDUAL_V2_GENERATION_TIMEOUT = PENDING_PERFORMANCE_BENCHMARK`; no
timeout was chosen here. Residual job identity V2 must eventually distinguish
scientific cell, decision state/dense row, robot, candidate residual index and
replica/matched-stream identity — recorded, with the official job manifest
unmutated. Official generation remains **unauthorized**.

Residual learning stays optional under H4: if benchmarking shows generation is
operationally infeasible, the residual branch is disabled or removed — the horizon
and objective are **not** to be changed post hoc to make generation faster.

`PRIMARY_SYNTHETIC_ROTATION_AUGMENTATION = DISABLED`. RB-16 not begun.

## Provenance

The Phase-8 composite alone is no longer the residual label contract. The additive
composite `residual_label_contract_composite_v2.json` binds the historical V1
contract, the pipeline erratum, this V2 specification, the local-information
mapping, the RB-15 finding, the spec-V2 audit, the snapshot and matched-stream
modules, the budget addendum and the unchanged Phase-8 manifest. RB-17 must
reference it. No historical hash was rewritten.

## Scope counters

RB-15 producer not implemented. Supervision rows 0. Recoverability rows 0. Shards
0. New FD24 checkpoints 0. Optimizer states 0. Training operations 0. Final-test
accesses 0. Study A N=24 accesses 0.
