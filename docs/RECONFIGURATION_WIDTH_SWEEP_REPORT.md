# Reconfiguration Width Sweep (Task 5-4)

Predeclared grid, N = 6, 12 width cells × 5 policies × 2 geometry variants ×
3 seeds. **Every cell is reported.** Raw: `results/reconfiguration_width_sweep/`

`h` = wall half-separation (inner obstacle centres at ±h).
`h_line = 0.550`, `h_keep = 1.450`, `h(α) = h_line + α(h_keep − h_line)`.

---

## 1. Complete sweep

| cell | h | width | KEEP cross | KEEP full | LINE cross | LINE full | KLK cross | KLK full | KL full | GEO full |
|---|---|---|---|---|---|---|---|---|---|---|
| infeasible control | 0.450 | 0.900 | **0.00** | 0.00 | **0.00** | 0.00 | **0.00** | 0.00 | 0.00 | 0.00 |
| α 0.05 | 0.595 | 1.190 | 0.00 | 0.00 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 |
| α 0.15 | 0.685 | 1.370 | 0.00 | 0.00 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 |
| α 0.25 | 0.775 | 1.550 | **0.00** | 0.00 | **1.00** | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 |
| α 0.35 | 0.865 | 1.730 | **0.00** | 0.00 | **1.00** | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 |
| α 0.45 | 0.955 | 1.910 | 0.33 | 0.00 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 |
| α 0.55 | 1.045 | 2.090 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 |
| α 0.65 | 1.135 | 2.270 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 |
| α 0.75 | 1.225 | 2.450 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 |
| α 0.85 | 1.315 | 2.630 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.33 |
| α 0.95 | 1.405 | 2.810 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.33 |
| keep-feasible control | 1.750 | 3.500 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.50 |

No cell was excluded, and no cell was chosen after the fact. Cells where
always-KEEP performs perfectly (α ≥ 0.55) are reported in full.

## 2. What the sweep establishes

**A genuine line-only band exists, and it is sharp.** Always-KEEP crossing is
**0.00 for h ≤ 0.865** and **1.00 for h ≥ 1.045**, with a single transitional
cell at h = 0.955 (0.33). Always-LINE crosses **1.00 from h = 0.595 upward**.
So for `0.595 ≤ h ≤ 0.865` — three geometrically distinct widths, two corridor
lengths, two entry offsets, three seeds — **LINE passes and KEEP cannot**.

The infeasible control is impassable for every policy (Gate G6 **passes**), and
the keep-feasible control is passable by everything.

This also explains the Task 4R fixture: it used h = 1.000, which sits inside the
transitional cell, which is why always-KEEP crossed it ~80 % of the time. That
fixture was never in the line-only band.

## 3. What the sweep does NOT establish

**No policy achieves full reconfiguration success inside the line-only band**,
and `full` is 0.00 for scripted KLK across the entire sweep — including cells
where the same controller and the same metric scored 1.00 in Task 4R.

That contradiction is diagnosed, not hidden. It is caused by **when the return
to KEEP is commanded**, not by the geometry:

| return timing on the same fixture | dwell achieved (need 20) |
|---|---|
| fixed step 55, i.e. **before** the team clears the exit | **38 / 48 / 51** → full 1.00 |
| at the exit plane (as this protocol predeclares) | **5 / 5 / 1** → full 0.00 |

The team crosses at step ≈ 85 and needs ≈ 54 steps to re-enter the keep tube.
Returning at the exit plane leaves ≈ 30 usable steps, and `E_inf` then oscillates
around the 0.55 threshold, so the 20-step dwell never completes.

## 4. The consequence for a decentralized policy

This is not merely a scripting detail. A robot's **only local evidence that the
passage is behind it is that its own clearance has reopened** — which is true
only *after* it exits. A purely local recovery trigger is therefore
**necessarily late**, by construction.

That is exactly what P5 shows: geometric event-triggered reconfiguration scores
`full = 0.00` in every constrained cell and reaches only 0.33–0.50 in wide
corridors where the passage is not binding.

To recover within the dwell, the team must begin re-forming *before* it has
cleared the passage — which requires either anticipation the current local
trigger cannot supply, a longer downstream leg, or a shorter required dwell.
None of those may be changed here: `L_recover = 20` and `epsilon_form = 0.55`
are frozen.
