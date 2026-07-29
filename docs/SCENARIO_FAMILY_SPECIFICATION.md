# Scenario Family Specification

Implementation: `rvt_swarm/layouts.py` · Splits: `docs/LAYOUT_SPLIT_PROTOCOL.md`

Every family is designed from **clearances**, not from what any model does well.
No learned model was run, consulted, or trained during this design.

## Shared physical constants

| Quantity | Value |
|---|---|
| Workspace | 12 × 12 m, x ∈ [−6, 6] |
| Robot radius `r` | 0.18 m |
| Obstacle radius `R` | 0.35 m |
| Robot–robot bound `d_rr` | 0.40 m |
| Robot–obstacle bound `d_ro` | 0.55 m |
| Nominal spacing `d₀` | 0.90 m |
| Start centre | (−4.56, 0) |
| Goal | (+4.56, 0), tolerance 0.55 m |
| Obstacle tile pitch | 0.70 m |

## The admissibility algebra that drives every design

For a **gate** built from two opposing obstacle rows whose innermost centres sit
at `y = ±W/2`, a robot centre is admissible only where `|y| ≤ W/2 − d_ro`. So the
half-channel is `c = W/2 − 0.55`, and:

| Mode | Lateral extent required | Gate width needed |
|---|---|---|
| `line` (single file along x) | ≈ 0 | **W ≥ 1.10 m** |
| `split` (two lanes at ±`lane_gap`/2, `lane_gap = max(d₀, d₀+d_rr) = 1.30`) | 0.65 m | **W ≥ 2.40 m** |
| `keep` (3-column grid, half-width `d₀` = 0.90) | 0.90 m | **W ≥ 2.90 m** |

That ordering is what makes the families separable:
`W ∈ [1.4, 2.2]` admits **only** `line`; a blocked centre column with side
channels admits **only** `split`; `W ≥ 2.9` admits all three.

---

## A. `keep_open` — keep-favourable

- **Geometry:** four sparse obstacles at `(±1.5, ±off)` and `(0, ±(off+1.2))`,
  `off ∈ {2.45, 3.25}` (validation). Corridor axis clear.
- **Expected feasible:** all modes. **Infeasible:** none.
- **Physical plausibility:** an open yard with scattered pillars.
- **Switching required:** no. **Fixed mode sufficient:** yes (`keep`).
- **Role:** the null family. If `keep` does *not* dominate here, the recovery
  event or the dynamics are miscalibrated.

## B. `line_corridor` — line-favourable

- **Geometry:** one gate at `x = gate_x`, width `W ∈ {1.50, 1.80, 2.10}` (val),
  wall tiles to `|y| = 3.6`.
- **Half-channel:** `c = W/2 − 0.55 ∈ {0.20, 0.35, 0.50}` — admits a single file
  (needs 0), excludes `split` (needs 0.65) and `keep` (needs 0.90).
- **Expected feasible:** `line`. **Infeasible:** `keep`, `split`.
- **Physical plausibility:** a doorway or aisle narrower than the team's width.
- **Switching required:** not strictly — `line` for the whole episode may suffice.
- **Role:** does `line` ever become the oracle-best mode?

## C. `split_around` — split-favourable

- **Geometry:** a single blocker at `(gate_x, 0)` **plus** outer walls at
  `|y| = outer_half ∈ {1.60, 1.80}` (val).
- **Admissible band:** `0.55 ≤ |y| ≤ outer_half − 0.55`, i.e. `[0.55, 1.05]` or
  `[0.55, 1.25]`. A split lane at `|y| = 0.65` fits; a single file at `y ≈ 0` is
  blocked by the central obstacle; a 3-column grid needs its centre column at
  `y = 0`, also blocked.
- **Expected feasible:** `split`. **Infeasible:** `keep`, `line`.
- **Physical plausibility:** a pillar mid-corridor with passable space each side.
- **Switching required:** no. **Role:** does `split` ever become oracle-best?

> **Known geometric tightness, stated up front.** The lane offset (0.65 m) clears
> the central obstacle by only 0.10 m beyond `d_ro`. This family is therefore a
> *narrow* test of `split`, and a negative result here may reflect the template's
> fixed lane gap rather than the absence of split-favourable geometry in general.

## D. `keep_line_keep` — transition family

- **Geometry:** two gates of the same width at `gate_x ± 0.5`, forming a 1.0 m
  corridor; open before and after.
- **Expected sequence:** `keep` → `line` → `keep`.
- **Switching required:** hypothesised yes — but this is a hypothesis, and
  `switch_necessity` is measured, not assumed.

## E. `keep_split_merge` — transition family

- **Geometry:** two blockers at `gate_x ± 0.5` on the axis plus outer walls; open
  approach and exit, single shared goal.
- **Expected sequence:** `keep` → `split` → merge back to `keep`.
- **Switching required:** hypothesised yes; measured.

## F. `ambiguous` — low-margin

- **Geometry:** one gate of width `W = gate_width_max + {1.4, 1.8}` ≈ 3.5–3.9 m,
  wide enough for every mode.
- **Expected feasible:** all. **Role:** measure ranking stability where modes tie.
  Expected to produce mostly *unqualified* states (near-ties), which is the point.

## G. `infeasible` — no feasible mode

- **Geometry:** a gate of width `W ∈ {0.80, 0.95}` — **below the 1.10 m single-file
  minimum**, so no robot centre is admissible anywhere in the gate.
- **Expected feasible:** none.
- **Role:** confirm the pipeline reports "no viable mode" instead of manufacturing
  a winner. If any mode shows a high recovery rate here, the recovery event is
  too easy or the collision model is wrong.

---

## Hypotheses versus labels

The table below records **hypotheses**. `layouts.mode_feasibility_hypothesis`
computes them from clearances, and they are used **only** for this document and
for a sanity test that the families differ. Every empirical `best_mode` label in
`results/scenario_headroom/` comes from rollout outcomes alone.

| Family | keep | line | split | switching hypothesised |
|---|---|---|---|---|
| A `keep_open` | ✓ | ✓ | ✓ | no |
| B `line_corridor` | ✗ | ✓ | ✗ | no |
| C `split_around` | ✗ | ✗ | ✓ | no |
| D `keep_line_keep` | ✗ in corridor | ✓ | ✗ | yes |
| E `keep_split_merge` | ✗ at blocker | ✗ | ✓ | yes |
| F `ambiguous` | ✓ | ✓ | ✓ | no |
| G `infeasible` | ✗ | ✗ | ✗ | n/a |

If the measured labels contradict these hypotheses, **the measurements win** and
the contradiction is itself a reportable finding about the mode templates.
