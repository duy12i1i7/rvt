# Local Controller Reconfiguration Qualification V2

Supersedes `LOCAL_CONTROLLER_RECONFIGURATION_QUALIFICATION.md`, whose recovery
conclusion was withdrawn (`TASK4_INVALID_EVALUATION_NOTICE.md`).

V3 metric · N = 6 only · 5 seeds per probe · scripted modes and the robot-local
controller · **no learned selector** · **no final-test layouts**.
Results: `results/local_controller_reconfiguration_qualification_v2/`

---

## 1. Verdict

> ### **C — The local controller completes scripted KEEP → LINE → KEEP under valid geometry and the V3 metric.**

`6_K_to_L_to_K` achieves **full reconfiguration success 1.00 across all five
seeds**, with post-exit `E_inf^KEEP` reaching 0.250 against the 0.55 tolerance
and the 20-step recovery dwell completing.

Not A: the evaluation is now valid — the metric admits success (`always_keep`
in the open fixture scores 1.00), episodes start inside the KEEP tube
(`E_inf(0) = 0.0848`), and the negative control is genuinely impassable.
Not B: recovery demonstrably completes.

## 2. Probe results

| probe | fixture | full | cross | recovered | `E_inf^KEEP` after exit (mean / min) | goal | coll-free |
|---|---|---|---|---|---|---|---|
| 1 always KEEP | open | **1.00** | 1.00 | 1.00 | 0.064 / — | 1.00 | 1.00 |
| 2 always LINE | open | 0.00 | 1.00 | **0.00** | 1.734 / — | 1.00 | 1.00 |
| 3 always KEEP | corridor | 0.80 | 0.80 | 0.80 | 1.668 / 0.191 | 0.80 | 1.00 |
| 4 always LINE | corridor | 0.00 | **1.00** | **0.00** | 1.998 / 1.838 | 1.00 | 1.00 |
| 5 K→L, no return | corridor | 0.00 | 1.00 | **0.00** | 1.967 / 1.834 | 1.00 | 1.00 |
| **6 K→L→K** | corridor | **1.00** | 1.00 | **1.00** | 0.634 / **0.250** | 1.00 | 1.00 |
| 7 K→L late | corridor | 0.00 | 1.00 | 0.00 | 1.949 / 1.826 | 1.00 | 1.00 |
| 8 L→K early | corridor | **1.00** | 1.00 | 1.00 | 0.378 / 0.181 | 1.00 | 1.00 |
| 9 K→L→K | **infeasible** | 0.00 | **0.00** | 0.00 | — | 0.00 | 0.40 |

The task separates exactly as designed: **probe 4 navigates perfectly** (crossing
1.00, goal 1.00, collision-free 1.00) and scores **0.00** on reconfiguration
because it never returns to KEEP. Probe 5 confirms this is the return, not the
crossing — same crossing, same goal, zero recovery. The negative control (9)
fails to cross at all.

## 3. Answers

| # | question | answer |
|---|---|---|
| 1 | Are `epoch.py` and `comm_cost.py` executed by the real runtime? | **Yes** — spies fire on `local_trigger`, `simulate_trigger_consensus`, `simulate_confirm_consensus`, `commit_or_retain` during real episodes |
| 2 | Is the inline periodic path removed from deployable execution? | **Yes** — only `legacy_periodic_epoch_baseline`, which raises under strict mode |
| 3 | Does confirmation prevent partial commitment? | **Yes** — delay beyond `Delta_stale` makes every robot retain; one mode across the team |
| 4 | Can the controller execute KEEP? | **Yes** — 1.00 full success in the open fixture |
| 5 | Can it execute LINE? | **Yes** — crossing 1.00, collision-free 1.00 |
| 6 | Can it execute KEEP → LINE? | **Yes** — probes 5, 6, 8 all cross 1.00 |
| 7 | Can it execute LINE → KEEP? | **Yes** — settles from the line template to `E_inf = 0.30` in ~54 steps |
| 8 | Can it complete KEEP → LINE → KEEP? | **Yes — 1.00 across 5 seeds** |
| 9 | Is final KEEP recovery physically achievable? | **Yes**, given ~74 steps of downstream travel after the exit plane |
| 10 | Are communication bytes from actual runtime messages? | **Yes** — counted at the send site from real serialized objects |

## 4. Why the earlier run said otherwise

Three defects, all repaired, none by relaxing a threshold:

| defect | repair | evidence |
|---|---|---|
| pairwise metric at a per-robot tolerance | V3 per-robot `E_inf` | `always_keep` moved from median 0.861 (outside) to 0.435 (inside) on the same episode |
| episodes began outside the KEEP tube (`E_inf(0) = 3.018`) | spawn on the role template | `E_inf(0) = 0.0848` |
| 12 m world too small for the mission | fixture world 18 m, sized from measured settling | 40 → 87 steps after crossing; dwell 0–5 → 38–51 |

`epsilon_form = 0.55` and `L_recover = 20` are unchanged throughout.

## 5. Findings that constrain Task 5

1. **N = 4 and N = 3 are excluded.** `delta_N` = 1.0062 and 0.6708 against the
   1.10 threshold; the midpoint configuration provably lies in **both** tubes.
   At those team sizes `always_line` could satisfy nominal recovery without
   leaving line. Only N = 6 is certified.
2. **The world must be ~18 m, not 12 m.** A full N = 6 mission needs ~74 steps
   after the exit plane; 12 m affords ~40 and the episode ends on goal arrival
   first.
3. **A "line-only" corridor is not line-forcing.** `always_keep` crosses the
   corridor on 80 % of episodes because the controller's avoidance term
   compresses the formation. Task 5's families will need narrower corridors or
   an explicit deformation bound.
4. **Epoch churn is 16.2 per traversal against an ideal of 2.** The no-op guard
   cuts protocol traffic 23 %, but the trigger still refires whenever the local
   geometry keeps satisfying it. Rate-limiting the trigger is deferred to
   Task 5.

## 6. Scope

5 seeds per probe, one fixture per condition, N = 6. **No robustness or
superiority claim is made.** No learned selector was trained, loaded or
evaluated. No final-test layout was accessed at any point.

Clean-checkout verification: **562 tests pass**, `guards.audit()` **0
violations**, strict mode enabled.
