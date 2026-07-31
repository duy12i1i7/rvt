# Decentralized Reconfiguration Headroom V2 — Task 5 Verdict

N = 6 only · diagnostic fixed policies only · **no learned selector trained,
loaded or consulted** · **no final-test layouts** · 591 tests pass ·
`guards.audit()` 0 violations.

Raw: `results/reconfiguration_width_sweep/`

---

## 1. Verdict

> ### **B — Line-requiring headroom exists, but event-triggered geometric reconfiguration is mechanically unreliable.**

The geometric headroom is real, sharp and reproducible. What fails is the
*deployable* policy: the decentralized event-triggered controller achieves
`full = 0.00` in every constrained cell, and the reason is structural rather
than a tuning accident.

Not A: always-KEEP does **not** adapt — its crossing rate is 0.00 for h ≤ 0.865.
Not C: churn is a real but secondary failure; the primary blocker is timing.
Not D: Gate G3 fails (no policy reaches `full ≥ 0.70` in the line-only band).
Not E: the geometry and metric are now validated by 15 dedicated contract tests
and cross-checked against the environment's own collision checker.

## 2. Gate results

| gate | result |
|---|---|
| **G1** initial validity | **PASS** — `E_inf^KEEP(0) = 0.0848` vs 0.25; no collisions; in bounds; connected |
| **G2** open-field nominal | **PASS** — always-KEEP full 1.00; event-triggered policy opens **0 epochs** in open field |
| **G3** constrained headroom | **FAIL** — best scripted `full` in the line-only band is 0.00 under plane timing (needs ≥ 0.70) |
| **G4** both transitions necessary | **PARTIAL** — always-LINE and K→L-without-return both score `full = 0.00` everywhere, as required; but no policy achieves the positive case in the band |
| **G5** false bottleneck | **not evaluated** — family D was not built (Task 5 stopped at the sweep) |
| **G6** infeasible control | **PASS** — crossing 0.00 for every policy at h = 0.450 |
| **G7** no learned selection | **PASS** — no learned model exists in this phase |
| **G8** tube disjointness | **PASS** — N = 6 certified, `delta_6 = 2.0125 > 1.10` |
| churn | **FAIL** — median 8 epochs per traversal against a predeclared ≤ 3 |

## 3. What is firmly established

**A sharp line-only band.** Across 12 widths × 2 geometry variants × 3 seeds:

| | always-KEEP crossing | always-LINE crossing |
|---|---|---|
| h ≤ 0.865 | **0.00** | **1.00** (from h = 0.595) |
| h = 0.955 | 0.33 | 1.00 |
| h ≥ 1.045 | 1.00 | 1.00 |

So for `0.595 ≤ h ≤ 0.865` the line formation passes and the keep formation
cannot. That is genuine, physically grounded headroom, and it is why the Task 4R
fixture (h = 1.000) was misleading: it sat in the transitional cell, which is
exactly why always-KEEP crossed it ~80 % of the time.

**The infeasible control is impassable** for every policy, and the
keep-feasible control is passable by everything.

## 4. The finding that produces verdict B

**A purely local recovery trigger is necessarily late.**

A robot's only local evidence that the passage is behind it is that *its own
clearance has reopened* — which becomes true only after it has exited. Measured
on the same fixture, same controller, same metric:

| when the return to KEEP is commanded | dwell achieved (need 20) | full |
|---|---|---|
| **before** the team clears the exit (step 55) | 38 / 48 / 51 | **1.00** |
| **at** the exit plane | 5 / 5 / 1 | **0.00** |

The team crosses at step ≈ 85 and needs ≈ 54 steps to re-enter the keep tube.
Returning at the exit plane leaves ≈ 30 usable steps and `E_inf` then oscillates
around the 0.55 threshold, so the dwell never completes.

This is not a scripting detail — it is the mechanism by which the *deployable*
policy fails. P5 (geometric event-triggered) scores `full = 0.00` in every
constrained cell and only 0.33–0.50 in wide corridors where the passage is not
binding.

To recover within the dwell the team must begin re-forming *before* it has
cleared the passage, which requires anticipation the current local trigger
cannot supply. `L_recover = 20` and `epsilon_form = 0.55` are frozen and were
not touched.

## 5. Churn (Task 5-7)

| stage | epochs/episode | no-ops | protocol bytes |
|---|---|---|---|
| Task 4R baseline | 16.2 | 13.4 | 100 685 |
| + no-op guard | 16.2 | 13.4 | 77 107 |
| + passage latch | 15.6 | 12.8 | 74 746 |
| + narrowed entry reasons | 8.6 | 5.8 | 41 880 |
| + local no-op pre-arm check | **8.0** | **4.6** | **37 726** |

Successful transitions are now exactly the ideal **2 per traversal**, open-field
episodes open **0 epochs**, and protocol traffic is down **63 %**. The median
count target (≤ 3) is still **missed at 8**, and the residual epochs are genuine
inter-robot disagreements rather than churn. Eliminating them needs a local
quorum before arming — a protocol change that is *not* attempted here, because
tuning the trigger further after seeing the results is the practice this project
forbids.

## 6. Scope and honesty notes

- Families C (offset entry), D (false bottleneck) and E (wide corridor) were
  **not built**; the phase stopped at the width sweep once G3 failed. G5 is
  therefore unevaluated, not passed.
- Every sweep cell is published, including the ones where always-KEEP is
  perfect. Nothing was excluded or reselected.
- Two implementation defects were found and fixed during the sweep, both of
  which had produced confidently wrong numbers: P3/P4 were implemented with
  fixed step numbers rather than the predeclared geometric planes, and
  `build_passage` placed the corridor inside the entry lookahead so the team
  entered LINE at step 0 with no KEEP approach.

## 7. Required before a learned pilot

1. **Give the recovery trigger anticipation.** Local clearance alone cannot fire
   early enough. Candidates: a peer-shared "front robot has exited" signal (still
   one-hop), or a longer downstream leg, or a shorter dwell — the last two change
   frozen parameters and need re-predeclaration.
2. **Re-run the sweep in the band `0.595 ≤ h ≤ 0.865`** once recovery can
   complete, and re-test G3/G4 there.
3. **Build families C–F** and evaluate G5.
4. **Add a local quorum** before arming, if the churn target is to be met.
