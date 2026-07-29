# Recovery Event Specification (Task 7)

The binary recovery event is defined **independently of the shaped rollout
utility** that the legacy training targets regress. It is a conjunction of
physical conditions, not a weighted sum.

Sensitivity data: `results/scenario_headroom/recovery_event_sensitivity.csv`
Script: `scripts/recovery_event_sensitivity.py` · **Validation layouts only.**

## 1. Definition

A rollout from state `x` holding mode `τ` for horizon `H` is **recovered** iff
**all** of the following hold:

1. no robot–robot collision at any step;
2. no robot–obstacle collision at any step;
3. centroid goal progress over the horizon ≥ `MIN_PROGRESS`;
4. the swarm enters the mode-conditioned formation tube
   (`form_rms < tube_scale · formation_tolerance`);
5. it remains inside that tube for at least `L` **consecutive** steps;
6. no deadlock;
7. no irreversible collapse.

Failure of any single condition returns 0. There is no partial credit, no
weighting, and no tunable coefficient — which is the point: the shaped utility
`R(x;τ)` in `recoverability.py:45` averages eight normalised terms and can trade a
collision against progress. This event cannot.

## 2. Parameters and the predeclared sensitivity grid

| Parameter | Default | Grid |
|---|---|---|
| Horizon `H` | 14 steps (2.1 s) | 7, 14, 28 |
| Tube tolerance scale | 1.0 (`formation_tolerance` = 0.55 m) | 0.75, 1.0, 1.5 |
| Dwell `L` | 3 steps | 1, 3, 5 |
| Minimum progress | 0.02 normalised | 0.01, 0.02, 0.05 |
| Rollouts per (state, mode) | 4 | fixed |
| Perturbation | pos σ = 0.02 m, accel σ = 0.03 m/s² | fixed |
| Rollout seed | 20 250 730 | dedicated stream |

The grid was fixed before running. **Values are not chosen to maximise any
model's AUROC** — no learned model is evaluated in this task at all. The
selection rule, also fixed in advance, is stated in §3.

## 3. Selection rule, fixed before observing results

The default parameter set is retained unless it fails a stability requirement:

| Requirement | Threshold |
|---|---|
| S1 — not too easy | pooled positive rate ≤ 0.85 |
| S2 — not too rare | pooled positive rate ≥ 0.15 |
| S3 — label stability | ≥ 80 % of (state, mode) labels unchanged under a one-step move in any single grid axis |
| S4 — discriminative | at least 20 % of states have a non-uniform label across the three modes |
| S5 — `infeasible` family sanity | positive rate ≤ 0.05 on family G |

If more than one grid point satisfies S1–S5, the **default** is kept — not the one
that maximises any downstream number. If the default fails, the nearest satisfying
point is chosen and the substitution is recorded here with its justification.

## 4. Reporting

Reported per grid point: positive-outcome prevalence overall, by scenario family,
and by mode; label-flip fraction against the default; and the fraction of
non-uniform states. The verdict — too easy, too rare, unstable, or acceptable —
follows mechanically from S1–S5.

## 5. Relationship to the legacy target

The legacy score head regresses `tanh(q/|q̄|)` where `q` is the shaped
horizon-averaged utility. **The event defined here is not that quantity**, and the
Method Audit measured the gap: the shaped utility reached AUROC 0.918 against the
event while the learned distillation reached 0.808. Any future score head intended
to predict *recovery* should be trained on this binary event with a proper scoring
rule (BCE), not on the shaped utility — that change is recommended but is **not**
made in this task, which introduces no new module.

## 6. Known limitations

- The rollout policy is the heuristic expert, so the event measures *the expert's*
  ability to recover under a mode, not the learned policy's.
- 4 rollouts per (state, mode) quantises the empirical rate to 0.25.
- Perturbations are the only stochasticity; the simulator is otherwise
  deterministic, and no sensor or actuation noise model exists.
- Conditions 4–5 use the mode-conditioned tube, so a mode that reshapes the
  formation is judged against its own target — intended, but it means the event is
  not mode-neutral.
