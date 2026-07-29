# Split Mode Validation (Task 8)

Raw data: [`../results/scenario_headroom_v2/split_mode_validation.csv`](../results/scenario_headroom_v2/split_mode_validation.csv)
Script: `scripts/validate_split_mode.py` · Deterministic (no perturbation), oracle-only, no learned model.

Split was **not** preserved by assumption. The question asked was whether it can be
shown to work at all.

---

## 1. Template geometry audit (scenario-independent)

The split template places two lanes at `± lane_gap/2` where
`lane_gap = max(d₀, d₀·scale + d_rr)`.

| formation scale | lane gap | lane offset | clears a central obstacle? | margin |
|---|---|---|---|---|
| 1.000 (nominal) | 1.300 m | 0.650 m | **yes** | **+0.100 m** |
| 0.500 (`min_formation_scale`) | 0.900 m | 0.450 m | **no** | **−0.100 m** |

**The template is infeasible at its own compression floor.** Under maximum
compression — exactly the regime a bottleneck induces — the commanded lane centre
sits 0.100 m *inside* the robot–obstacle bound (0.55 m) relative to an obstacle on
the corridor axis. The controller is instructed to drive robots into a violation.

Even at nominal scale the margin is only 0.100 m, against a per-step travel of
`v_max·Δt = 0.135 m`. **A single control step of tracking error exceeds the entire
clearance budget.**

## 2. Deterministic traversal, fixed mode (no perturbation)

Goal at x = 4.56. `maxX` = furthest centroid x reached.

| family | N | mode | crossed | goal | coll-free | success | maxX | exit_x |
|---|---|---|---|---|---|---|---|---|
| `split_around` | 4 | keep | 1.00 | **1.00** | 1.00 | **1.00** | 4.06 | 1.15 |
| | 4 | line | 1.00 | **1.00** | 1.00 | **1.00** | 4.06 | 1.15 |
| | 4 | **split** | 1.00 | **0.00** | 1.00 | **0.00** | **2.49** | 1.15 |
| `split_around` | 6 | keep | 1.00 | 1.00 | 1.00 | 0.50 | 4.09 | 1.15 |
| | 6 | line | 1.00 | **1.00** | 1.00 | **1.00** | 4.06 | 1.15 |
| | 6 | **split** | 1.00 | **0.00** | 1.00 | **0.00** | **3.17** | 1.15 |
| `keep_split_merge` | 4 | keep | 1.00 | 1.00 | 1.00 | 1.00 | 4.03 | 1.65 |
| | 4 | line | 1.00 | 1.00 | 1.00 | 1.00 | 4.08 | 1.65 |
| | 4 | **split** | 0.50 | **0.00** | 1.00 | **0.00** | **1.88** | 1.65 |
| `keep_split_merge` | 6 | **split** | 1.00 | **0.00** | 1.00 | **0.00** | **2.42** | 1.65 |
| `line_corridor` | 4 | **split** | **0.00** | **0.00** | 1.00 | **0.00** | **−0.69** | 0.65 |
| `line_corridor` | 6 | keep | 1.00 | **0.00** | 1.00 | **0.00** | 1.86 | 0.65 |
| | 6 | **line** | 1.00 | **1.00** | 1.00 | **1.00** | 4.07 | 0.65 |
| | 6 | **split** | **0.00** | **0.00** | 1.00 | **0.00** | **−0.80** | 0.65 |

### Two facts stand out

**Split never reaches the goal. Not once, in any family, at any team size.**
It crosses the bottleneck in several cases and then stalls: 2.49, 3.17, 1.88,
2.42 against a goal at 4.56. In `line_corridor` it does not even approach the gate
(maxX ≈ −0.7 from a start at −4.56).

**Split never strictly beats keep on crossing: 0 wins, 14 losses, 14 ties.**

## 3. Diagnosis — which cause is it?

| Candidate cause | Verdict |
|---|---|
| Split mode not useful | **Contributing.** In every geometry tested, `keep` or `line` already crosses, so split has nothing to win |
| Infeasible geometry | **Confirmed at compression.** Lane offset 0.450 m vs a 0.55 m bound is a −0.100 m violation |
| Invalid formation template | **Confirmed.** The template commands an infeasible configuration at `min_formation_scale`, and has only a 0.100 m margin at nominal scale — smaller than one step of travel |
| Incorrect robot assignment | **Not the cause.** The audit confirms 2 subteams and a minimum commanded pair distance of 0.900 m at nominal scale, above the 0.40 m bound |
| **Continuation/merge weakness** | **Confirmed and probably decisive.** Split crosses but never completes. There is **no merge behaviour**: `always split` holds two lanes indefinitely, and nothing in the controller recombines them to satisfy the goal criterion |
| Insufficient horizon | **Ruled out.** T_max = 200 steps against episodes that `keep` finishes well within |
| Recovery-event mislabelling | **Ruled out.** These are raw episode metrics, not V2 labels |

The dominant cause is a **missing merge**, compounded by a template that is
geometrically infeasible exactly where it would be needed. Splitting is
implemented; *recombining* is not.

## 4. Could a demonstration be constructed?

Task 8 asks for a hand-built state where split is feasible, a scripted trajectory
that splits/traverses/merges, and a matching keep trajectory that fails.

- **Feasible state:** yes at nominal scale (+0.100 m margin), though tight.
- **Split-traverse-merge trajectory:** **cannot be produced without adding a merge
  controller** — a new module, which this task forbids, and which would in any case
  be building the mechanism in order to justify it.
- **Keep failing where split succeeds:** **no such case was found.** In all 14
  paired comparisons, keep crossed whenever split did.

Producing a favourable demonstration would require *both* changing the template
geometry *and* adding a merge behaviour, then searching for a scenario where the
result wins. That is tuning a mechanism into existence against a target outcome,
which the task explicitly prohibits.

## 5. Outcome

> ### **C — split is removed, leaving keep/line selection.**

Not A (validated): it never completes a task and never beats keep on crossing.
Not B (future work): "future work" implies the mechanism is sound but untested; it
is neither — the template is infeasible at compression and the merge does not
exist. Recording it as future work would overstate its maturity.
Not D (remove all modes): **`line` is validated by the same experiment** —
`line_corridor` N=6 is the clean case where keep crosses the gate but stalls
(maxX 1.86, goal 0.00) while line completes (maxX 4.07, goal 1.00, success 1.00).

## 6. Consequences

1. The mode set becomes `{keep, line}`; `T` shrinks from 3 to 2.
2. The score head emits 2 values, and the action bank 2 slices.
3. `split_around` and `keep_split_merge` lose their reason to exist as families;
   `split_around` retains value only as a *keep-vs-line* obstacle scenario.
4. Everything the manuscript says about splitting into coordinated subteams must
   be removed — it describes a mechanism that has never completed a task.
5. **If split is ever revisited**, it needs: a lane gap derived from the actual
   obstacle clearance rather than from `d₀`, an explicit merge controller, and a
   scenario where keep provably cannot pass. All three, before any claim.

## 7. Limitations

- Deterministic runs, one seed per cell, N ∈ {4, 6}, three families.
- Only the *implemented* split template was tested. This is evidence about **this
  implementation**, not a claim that subteam splitting is useless in general.
- Larger teams (N ≥ 12), where a single file becomes long and splitting might pay,
  were not tested.
