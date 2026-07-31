# Decentralized Reconfiguration Task V2

Replaces permanent keep-versus-line selection, which the seed-0 dry run showed
to be an invalid scientific task: `always_line` succeeded in **all four**
validation families (1.000), so no selector could demonstrate value.

The task is now

> **nominal keep → temporary line for constrained passage → recovery to nominal keep**

The distinction is created by a **mission requirement** — the nominal formation
must be recovered — and not by any numerical penalty added to make keep win.
Staying in line after the passage simply does not accomplish the mission, in the
same way that a convoy that never re-forms has not finished manoeuvring.

---

## 1. Notation

`N` robots, positions `p_i(t) ∈ ℝ²`, persistent roles from
`RoleAssignment` (`roles.py`). `R(ψ)` rotates the template into the shared
mission frame. Pairwise desired offset

```
d_ij^τ = R(ψ_mission) [ r_j^τ − r_i^τ ],     τ ∈ {keep, line}
```

exactly antisymmetric, computable by robot *i* from its own role, the
neighbour's communicated role, and the shared mission direction.

Constants from `EnvConfig`: `s = 0.9` (nominal spacing), `ρ = 0.18`
(robot radius), `d_ro = 0.55` (robot–obstacle clearance),
`d_rr = 0.40` (robot–robot clearance), `ε_form = 0.55` (formation tolerance),
`Δt = 0.15 s`.

## 2. Formation sets

Both sets use the **pairwise** formation error, not a centroid-referenced one.
This is deliberate: it is translation-invariant, it is exactly the quantity the
robot-local controller regulates, and it requires no global reference even
conceptually.

```
E_τ(t) = max over formation-neighbour pairs (i,j) of ‖ (p_j(t) − p_i(t)) − d_ij^τ ‖
```

**Nominal formation set (keep tube)**

```
𝒦 = { X : E_keep(X) ≤ ε_form }
```

**Line transit set**

```
ℒ = { X : E_line(X) ≤ ε_form }
```

**`𝒦 ∩ ℒ = ∅` for `N ≥ 3`**, verified rather than asserted. A configuration in
both sets would need every pair within `ε_form` of *both* templates, which by the
triangle inequality requires `max_ij ‖d_ij^keep − d_ij^line‖ ≤ 2 ε_form = 1.10 m`.
Measured:

| N | `max_ij ‖d_ij^keep − d_ij^line‖` | `2 ε_form` | disjoint |
|---|---|---|---|
| 3 | 1.273 m | 1.100 m | yes |
| 4 | 2.012 m | 1.100 m | yes |
| 6 | 4.025 m | 1.100 m | yes |

So "in keep formation" and "in line formation" are mutually exclusive: no episode
can satisfy both at once, and a team that remains in line can never satisfy the
recovery condition. This is the load-bearing fact behind §5 — if the two sets
overlapped, `always_line` could satisfy the mission by accident.

### 2.1 Template widths — where the headroom comes from

Computed directly from the templates (`RoleAssignment.from_index`), the corridor
width a formation needs is its lateral extent plus clearance on both sides,
`W_req = lateral_extent + 2(ρ + d_ro)`:

| N | formation | lateral extent | longitudinal | **W_req** |
|---|---|---|---|---|
| 4 | keep | 0.90 m | 0.90 m | **2.36 m** |
| 4 | line | 0.00 m | 2.70 m | **1.46 m** |
| 6 | keep | 1.80 m | 0.90 m | **3.26 m** |
| 6 | line | 0.00 m | 4.50 m | **1.46 m** |

This yields four physically distinct corridor bands:

| corridor width `W` | N=4 | N=6 |
|---|---|---|
| `W < 1.46` | infeasible for both | infeasible for both |
| `1.46 ≤ W < 2.36` | **line only** | **line only** |
| `2.36 ≤ W < 3.26` | keep feasible | **line only** |
| `W ≥ 3.26` | keep feasible | keep feasible |

The band `2.36 ≤ W < 3.26` is where N=4 and N=6 disagree, and
`1.46 ≤ W < 2.36` is line-only for both. These are hypotheses about physical
feasibility, to be **qualified empirically** in Task 7 with diagnostic
controllers — never assumed.

> Note: `layouts.py` currently states `keep ≥ 2.90 m` and `line ≥ 1.10 m` under a
> different clearance convention. The values above are recomputed from the actual
> templates and the actual `EnvConfig` constants and supersede them for V2. The
> discrepancy is recorded rather than silently reconciled.

## 3. Regions

Let `𝒮` be the constrained obstacle structure and `x` the coordinate along the
shared mission direction (`regions.py` already provides this construction).

**Entry plane** — far enough upstream that a robot cannot be inside the
structure's clearance envelope when it crosses:
```
x_entry = min_x(𝒮) − (ρ + d_ro)
```

**Exit plane**:
```
x_exit  = max_x(𝒮) + (ρ + d_ro)
```

**Downstream recovery region** — beyond the exit plane and wide enough that the
nominal formation actually fits:
```
𝒟 = { p : x(p) ≥ x_exit + m_D  and  free_width(x(p)) ≥ W_req^keep(N) }
```
with margin `m_D = 0.5 m`. Without the width condition a scenario could demand
recovery in a place where recovery is geometrically impossible, which would make
the task unfair rather than hard. `𝒟` must be at least `L_D = 3.0 m` long along
the mission direction so the formation can be held while moving, not merely
touched at a point.

## 4. Events

**A — Bottleneck entry.** First time any robot crosses the entry plane:
```
t_entry = min { t : ∃i, x(p_i(t)) ≥ x_entry }
```

**B — Bottleneck crossing.** First time *every* robot is past the exit plane:
```
t_cross = min { t : ∀i, x(p_i(t)) ≥ x_exit }
```
A geometric fact about positions, requiring no formation judgement. Undefined
(`∞`) if the team never crosses.

**C — Nominal formation recovery.** After crossing, the team enters the keep
tube inside the recovery region and **holds it**:
```
t_rec = min { t ≥ t_cross :
              ∀u ∈ [t, t + L_recover),  X(u) ∈ 𝒦  and  ∀i, p_i(u) ∈ 𝒟 }
```

`L_recover = 20` control steps = **3.0 s**. Justification, fixed here in advance:
at `max_speed = 0.9 m/s` the team travels up to 2.7 m during the window, which
exceeds the keep template's own longitudinal extent (0.90 m) and its lateral
extent (1.80 m at N=6). The formation must therefore be maintained while
traversing more than its own footprint, so a transient clip of the tube boundary
cannot satisfy it. `L_recover` is **not** tuned against any policy's results.

**D — Full reconfiguration success.** All of:

1. the final goal / downstream mission region is reached;
2. no robot–robot collision at any step (`min_ij ‖p_i − p_j‖ > d_rr` throughout);
3. no robot–obstacle collision at any step;
4. no deadlock;
5. no irreversible collapse;
6. the bottleneck is crossed, where the scenario has one (`t_cross < ∞`);
7. the team returns to the nominal keep tube inside `𝒟`;
8. it is held for at least `L_recover` consecutive steps (`t_rec < ∞`).

All eight are episode-wide, evaluated under `EVALUATION_SCHEMA_VERSION = 2`
semantics — conjunction over the episode, never a terminal-step snapshot.

## 5. Why this restores headroom without a penalty

Conditions 7–8 are the whole change. Under them:

- **`always_keep`** satisfies 7–8 trivially but fails condition 6 in any corridor
  narrower than `W_req^keep(N)` — it cannot get through.
- **`always_line`** can satisfy condition 6 but **cannot satisfy 7–8 at all**,
  because `𝒦 ∩ ℒ = ∅`: a team that stays in line is never in the keep tube. This
  is exactly the arm that scored 1.000 on the old task and made it vacuous.
- **`keep → line → keep`** is the only diagnostic policy that can satisfy all
  eight in a line-only corridor.

No term was added to the objective and no constant was chosen to disadvantage
line. Condition 7 is the mission requirement that the nominal formation be
recovered; line's failure follows from the geometry of the two templates.

## 6. What is measured, and where

Global state is used **only** for offline metric computation — an explicitly
permitted use. `E_keep`, `t_cross`, `t_rec` and conditions 1–8 are scored by the
evaluator after the fact. No robot computes any of them: a robot's own trigger
uses only its own sensed clearance, its own progress, and its own local
formation error (§`epoch.local_trigger`).

The runtime remains: robot-local observations + one-hop peer communication +
robot-local ego-GNN + leaderless neighbour consensus + event-triggered local mode
commitment + robot-local formation controller.

## 7. Carried forward unchanged

Recovery Event V2 · split mode remains removed · no topology-switching
*claim* is made (the mode sequence is now part of the task definition, not a
claimed capability) · no learned action heads · no global selector · disjoint
train/validation layout geometry · **no final-test access**.
