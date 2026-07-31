# Recovery Propagation Latency Repair — Report and Verdict

Branch `research/recovery-propagation-latency-repair-v1` from tag
`decentralized-recovery-proposal-repair-v1`. N = 6 · diagnostic policies only ·
**no learned selector** · **no final-test layouts** · `R_obs`, `epsilon_form`,
`L_recover`, persistence, consensus rounds, commitment duration and corridor
geometry **all unchanged** · 604 tests pass · 0 guard violations.

---

## 1. Verdict

> ### **C — The repair is mechanically correct, but full recovery remains below the predeclared gate.**

Latency is now essentially optimal (2 steps after evidence, all of it the frozen
persistence rule), and two of the three cells clear the 0.70 bar. The complete
three-cell set does not.

Not A: the delay is decomposed exactly and contributes zero beyond persistence.
Not B: event semantics are correct — adopting robots need no evidence of their own.
Not D: T4 fails on the complete set (crossing 0.67, full 0.50).
Not E: one trace per cell from the real runtime, exact arithmetic, 0 violations.

## 2. Results — complete frozen three-cell set (2 variants × 5 seeds each)

| cell | full (6R → now) | crossing | dwell | collision-free | median epochs | no-op | L→K step |
|---|---|---|---|---|---|---|---|
| α 0.25 | 0.10 → **0.00** | **0.00** | 0.00 | 1.00 | 2 | 0 | 66 |
| α 0.35 | 0.30 → **0.70** | 1.00 | 0.70 | 1.00 | 2 | 0 | 61 |
| α 0.45 | 0.50 → **0.80** | 1.00 | 0.80 | 1.00 | 2 | 0 | 54 |
| **pooled** | **0.50** | **0.67** | **0.50** | **1.00** | **2** | **0** | — |

**α 0.25 regressed to zero crossing.** Recovering earlier means the team begins
re-expanding while still inside the narrowest corridor, and it no longer gets
through. This is precisely the "early expansion inside the corridor" risk the
P4 gate named, and it is reported as a regression rather than averaged away.

## 3. Answers

1. **What caused the remaining delay?** A no-op *pre-arm* check added in
   Task 5-7 that re-derived the mode from `nearest_obstacle_clearance` and
   cancelled arming for a robot holding valid evidence — the same defect class as
   6R, one layer earlier.
2. **Was the protocol waiting for every robot to observe the opening?** **No.**
   Pre-repair, commitment tracked the *last* robot (evidence 44…103, commit 111).
   Post-repair it commits at 45–46, before any non-originator has evidence.
3. **Did the token preserve ENTRY vs RECOVERY semantics?** Yes — the direction is
   recovered deterministically from lifecycle state, and `requested_mode_for`
   never returns the currently committed mode.
4. **Do adopting robots derive requested mode consistently?** Yes — all derive
   KEEP; it is invariant to their own clearance.
5. **Which robot was on the critical path?** The foremost robot in the line —
   whichever that happens to be, not a designated role. It originates; the rest
   adopt.
6. **Did confirmation depend on local sensor evidence?** **No.** Confirmation
   votes on the accepted event's requested mode.
7. **Final nominal protocol latency?** **2 steps**, entirely the frozen
   `L_TRIGGER = 3` persistence rule. Propagation, score consensus and
   confirmation contribute **0**.
8. **Passes all three cells?** **No** — 0.00 / 0.70 / 0.80.
9. **No-op epochs still zero?** **Yes**, 0 across all 30 episodes.
10. **Median epoch count ≤ 3?** **Yes — 2** in every cell.
11. **Still fully decentralized and leaderless?** **Yes** — 0 guard violations,
    no exit plane, no centroid, no coordinator, each robot computes its own action.

## 4. Gates

| gate | result |
|---|---|
| **R1** exact explanation | **PASS** — decomposition sums exactly; protocol contributes 0 |
| **R2** event semantics | **PASS** — RECOVERY ⇒ KEEP for all accepting robots; no rediscovery required; no leader |
| **R3** nominal latency | **PASS** — 2 steps, within any reasonable `L_post_repair_max` |
| **R4** mechanical success | **FAIL** — crossing 0.67 (< 0.80), full 0.50 (< 0.70), dwell 0.50 (< 0.70); collision-free 1.00 **passes** |
| **R5** epoch control | **PASS** — no-op 0, median 2, exactly 2 successful transitions |
| **R6** decentralization | **PASS** — 0 violations |

## 5. Remaining blocker

Not latency, and not epoch control — both are now solved. The blocker is a
**timing trade-off in the narrowest corridor**: the forward-opening event fires
while the tail of the formation is still inside the passage, and re-expanding
there costs the crossing at α 0.25.

That is a genuine scientific question about the event's definition, not an
implementation defect, and addressing it would require changing the event or a
frozen parameter. Both are out of scope here.
