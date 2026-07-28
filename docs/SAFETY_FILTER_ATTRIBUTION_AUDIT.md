# Safety-Filter Attribution Audit (Task 2)

Is the learned policy or the safety filter doing the controlling?

Raw data: [`../results/method_audit/safety_filter_attribution.csv`](../results/method_audit/safety_filter_attribution.csv)
Script: `scripts/audit_safety_and_topology.py` · Benchmark tag: `benchmark-protocol-v2-smoke`

**Validation split only** (open_field + narrow_passage, N ∈ {5, 11}, 8 episodes
per cell = 32 episodes, 3 606 control steps). The threshold grid was
**predeclared in the script** before any run. No final-test scenario, seed, or
metric was used, and no threshold was selected on final-test performance.

Model: `checkpoints/method_audit/rvt_swarm.pt`, 30 epochs on 30 expert episodes,
checkpoint chosen on validation (epoch 30).

---

## 1. The headline correction

**The smoke benchmark's 88–92 % activation rate does not reproduce with a trained
model. It was an artifact of the 6-epoch smoke checkpoint.**

| | smoke model (6 epochs) | audit model (30 epochs) |
|---|---|---|
| Activation rate, narrow passage | 0.883 – 0.918 | **0.023 overall** |
| Topology switches / episode | 12.7 – 14.0 | **0.00** |

The mechanism is visible in the trigger reasons: **all 82 triggers came from
`all_topologies_negative`**, i.e. the recoverability-escalation path
(`safety.py:170-171`), and **none** from geometric risk. An undertrained score
head emits negative scores for every mode almost everywhere, which forces the
filter on. Once the score head is trained, that path almost never fires.

This retires smoke anomaly 8.2.1 as a model-maturity artifact, and replaces it
with a different and more consequential finding (§3).

## 2. Intervention statistics (shipped configuration)

| Quantity | Value |
|---|---|
| Activation rate | **0.023** |
| Relative intervention, mean (all steps) | 0.009 |
| Relative intervention, median (all steps) | 0.000 |
| p90 / p95 (all steps) | 0.000 / 0.000 |
| Steps with relative intervention > 0.10 | 0.022 |
| > 0.25 | 0.014 |
| > 0.50 | 0.006 |
| > 1.00 | **0.001** |
| Trigger reasons | `all_topologies_negative`: 82; `geometric_risk`: 0 |

`relative_intervention = ‖u_filtered − u_nominal‖ / max(‖u_nominal‖, ε)`,
averaged over robots per step.

**Reading:** on 97.7 % of steps the filter does nothing at all. When it does
fire, it fires because the *learned score* declared every mode unrecoverable —
not because geometry demanded it.

## 3. Filter on vs. filter off — the decisive comparison

| Variant | Success | Coll-free | Goal | Deadlock | Activation |
|---|---|---|---|---|---|
| **1. no filter** (nominal learned policy) | **0.312** | **0.750** | **0.406** | **0.062** | 0.000 |
| **2. current filter** (shipped) | **0.312** | **0.750** | **0.406** | **0.062** | 0.021 |

**Every metric is identical to three decimal places.** With a trained model on
validation scenarios, the safety filter changes nothing measurable.

So the answer to "is the filter the effective controller?" is **no — but not
because the learned policy is strong. Because the filter is inert.**

## 4. Predeclared risk-threshold grid

`risk_threshold ∈ {0.50, 0.65, 0.75, 0.85, 0.95}`. The shipped value is
geometry-derived: `ρ_th = 1 − v_max·Δt/d₀ = 0.85`.

| Threshold | Success | Coll-free | Goal | Deadlock | Activation |
|---|---|---|---|---|---|
| 0.50 | 0.312 | **0.781** | **0.500** | **0.156** | 0.925 |
| 0.65 | **0.344** | 0.719 | 0.469 | 0.094 | 0.389 |
| 0.75 | 0.312 | 0.750 | 0.406 | 0.062 | 0.024 |
| **0.85 (shipped)** | 0.312 | 0.750 | 0.406 | 0.062 | 0.021 |
| 0.95 | 0.312 | 0.750 | 0.406 | 0.062 | 0.022 |

**Trade-off:** driving the threshold down to 0.50 raises activation to 92.5 %,
buys +0.031 collision-free and +0.094 goal-reached, and costs **2.5× the
deadlock rate** (0.062 → 0.156). That is the classic safety-filter trade-off, and
it is the only place in this audit where the filter demonstrably does anything.

**Caution, stated plainly:** 32 episodes means one episode = 0.031. The
"best-success" cell (0.344 at threshold 0.65) is **one episode** above the others
and is not a meaningful difference. **No threshold is selected here**, and none
should be selected until a multi-seed validation study with many more episodes
exists. Reporting 0.65 as "the tuned value" would be fitting noise.

## 5. Comparison against a faithful CBF-QP

Not run as a *filter-substitution* variant. The repository's `cbf_qp`
(`baselines.py:210`) is a standalone controller — it applies the exact 2-D QP to
the **KEEP-expert nominal**, not to a learned nominal, so swapping it in would
change the nominal controller as well as the filter and confound the comparison.
Building a learned-nominal + CBF-QP variant would mean adding a module, which
Task 6 forbids.

**[REQUIRES NEW EXPERIMENT]** — a filter-substitution variant that applies
`_solve_per_robot_qp` to the learned nominal, with no blending. Until it exists,
the claim "our filter is better than a CBF-QP" cannot be made. Given §3 shows the
current filter is behaviourally inert, the more likely outcome is that both are
inert on validation and the comparison is uninformative at this scale.

## 6. Decision rules applied

| Rule | Applies? | Consequence |
|---|---|---|
| "If the filter activates on most steps and substantially changes the action, describe the system as a safety-controller-dominated hybrid" | **No** — 2.3 % activation, median relative intervention 0.000 | The system is **not** safety-controller-dominated. The smoke-based suspicion is withdrawn. |
| "If the learned policy fails without the filter, the paper must report this explicitly" | **No** — identical with and without | Nothing to report except that the filter is inert |
| "If CBF-QP performs similarly or better, the current filter cannot be a primary contribution" | Untested (§5) | Cannot be a primary contribution **regardless**, on §3 alone |
| "Do not tune a threshold merely to maximize RVT-Swarm success" | Honoured | No threshold selected; the 0.344 cell is explicitly called noise |

## 7. Verdict

**The risk-triggered safety projection is not a contribution and should be
removed from the method's claims.**

- It activates on 2.3 % of validation steps.
- Removing it changes **no** measured outcome.
- Its only trigger path is the learned score declaring universal
  unrecoverability — so it is a *symptom detector for a poor score head*, not an
  independent safety mechanism.
- Its blending step voids any forward-invariance property the QP would provide,
  so it never had a formal guarantee to claim.

Recommended treatment: move to an appendix as an optional runtime component,
described as a **CBF-inspired projection with blending, empirically inert on
validation scenarios at the tested scale**. Do not describe it as a safety
guarantee, a safety contribution, or a reason for any observed result.

## 8. Limitations

- One model seed, one training budget, 32 validation episodes. Differences below
  ≈0.06 in any rate are within one or two episodes.
- Validation scenarios are `open_field` and `narrow_passage` at N ∈ {5, 11}.
  Denser or larger teams could plausibly make the filter active again — the smoke
  run's N=8 narrow-passage cells did show high activation, albeit with an
  undertrained model.
- No noise model is active (deterministic mode), so the filter is never tested
  against sensing error, which is one of the conditions it would exist to handle.
