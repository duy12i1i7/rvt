# Mode Headroom — Definition and Qualification Criteria

**Written and committed before the scenario analysis was run.** These are
*benchmark qualification criteria*, not publication results, and no learned model
is involved at any point.

## 1. Quantities

For a decision state `x` and candidate mode `τ ∈ {keep, line, split}`, let
`R(x, τ) ∈ [0, 1]` be the **empirical recovery rate**: the fraction of perturbed
oracle rollouts from `x`, holding mode `τ`, that satisfy the binary recovery event
of [`RECOVERY_EVENT_SPECIFICATION.md`](RECOVERY_EVENT_SPECIFICATION.md).

| # | Quantity | Definition |
|---|---|---|
| 1 | `best_mode(x)` | `argmax_τ R(x, τ)`; ties broken toward `keep` (the conservative default) |
| 2 | `mode_margin(x)` | `R(x, best) − R(x, second-best)` |
| 3 | `keep_regret(x)` | `R(x, best) − R(x, keep)`; zero when `keep` is best |
| 4 | `selector_headroom` | `E_x[keep_regret(x)]` over qualified decision states |
| 5 | `mode_diversity` | empirical distribution of `best_mode(x)` over qualified states |
| 6 | `mode_necessity` | fraction of states where `R(x, keep) < 0.5 ≤ R(x, best)` — a non-keep mode turns a failing rollout into a recovering one |
| 7 | `switch_necessity` | fraction of episodes where no single fixed mode succeeds but some mode *sequence* does |
| 8 | `oracle_advantage` | episode success of the per-decision rollout oracle minus always-`keep` |

**Qualified decision state.** A state is qualified when at least one mode reaches
`R ≥ 0.5` (otherwise no mode is viable and the state says nothing about
*selection*) and not all modes tie exactly (a tie carries no ranking information).
Unqualified states are counted and reported separately, never silently dropped.

## 2. Qualification criteria — fixed before observing any result

A scenario family **qualifies** for the scientific pilot only if, on
**validation layouts**:

| # | Criterion | Threshold |
|---|---|---|
| C1 | No single mode dominates | no mode is `best_mode` in **> 70 %** of qualified states |
| C2 | `line` is genuinely used | **≥ 15 %** of qualified states prefer `line` |
| C3 | `split` is genuinely used | **≥ 10 %** of qualified states prefer `split` |
| C4 | Always-`keep` has measurable regret | `selector_headroom ≥ 0.05` in constrained families |
| C5 | The oracle beats always-`keep` | `oracle_advantage ≥ 0.10` episode success |
| C6 | Margins are not all near zero | median `mode_margin` over qualified states **≥ 0.10** |
| C7 | Some episodes require a transition | `switch_necessity > 0` in at least one family |

C1–C3 and C6 are evaluated **per family** where the family is intended to exercise
that mode, and **pooled across families** for the benchmark as a whole. C2 and C3
are pooled criteria: a `keep`-favourable family is not expected to prefer `line`.

## 3. Rules that bind this analysis

- **Rollout outcomes decide the labels.** The geometric feasibility hypotheses in
  `layouts.mode_feasibility_hypothesis` are stated as hypotheses and are never
  used as labels, never used to filter states, and never used to score a mode.
- **No learned model is used** at any point in scenario qualification.
- **Validation layouts only.** Final-test layouts are not loaded, not measured,
  and not examined.
- **Thresholds are not revised after seeing results.** If the benchmark fails a
  criterion, the honest outcome is that the benchmark fails it. Revising a
  threshold post hoc would make the criterion unfalsifiable, and any revision must
  be justified *and dated before* the run that it applies to.
- **No scenario is selected because it favours a particular method.** No method is
  run.

## 4. Interpretation guide, also fixed in advance

| Outcome | Meaning |
|---|---|
| C1 fails with `keep` dominating | mode selection has no headroom; a fixed policy is near-optimal and topology control cannot be the paper's idea |
| C2 or C3 fails | that mode is unused; the mode set should shrink, and claims about it must be dropped |
| C4/C5 fail | the oracle itself gains nothing, so *no* selector — learned or otherwise — can gain anything |
| C6 fails | modes are near-ties; ranking is measurable but decision-irrelevant |
| C7 fails | no episode needs a *transition*; per-episode fixed-mode selection suffices, and "switching" claims must go |
| Many unqualified states | the horizon, tube tolerance or dynamics make recovery unreachable — a benchmark defect, not a method result |
