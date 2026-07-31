# Recovery Trigger Timing Repair — Report and Verdict

Branch `research/recovery-trigger-timing-repair-v1` from tag
`decentralized-recovery-timing-discrepancy-v1`. N = 6 · diagnostic policies
only · **no learned selector** · **no final-test layouts** · `R_obs`,
`epsilon_form`, `L_recover`, persistence, consensus rounds, commitment duration
and corridor geometry **all unchanged** · 604 tests pass · 0 guard violations.

---

## 1. Verdict

> ### **C — The timing repair works, but closed-loop recovery remains mechanically unreliable.**

The discrepancy is fully explained and the repair is real and large: full
reconfiguration went 0.00 → **0.10 / 0.30 / 0.50** across the three cells, and
median epochs went **8 → 2**. But T4 requires full success ≥ 0.70 and the best
cell reaches 0.50, so recovery is not yet reliable.

Not A: the discrepancy is explained to the step, and the decomposition sums
exactly.
Not B: valid local evidence *does* now produce a materially earlier transition
(L→K step 117 → 88, 102 → 73).
Not D: T4 is not met.
Not E: one trace, one detector, exact arithmetic, 0 guard violations.

## 2. Answers

1. **Why did the audit see the opening at ~44 while the runtime committed near
   114?** The runtime *did* detect it at 44 and was armable from 46. It then
   proposed the mode it already held, because the proposal was re-derived from
   `nearest_obstacle_clearance` (0.872 m) instead of the event's requested mode.
   The no-op guard discarded the epoch 25 times.
2. **Different observations or detectors?** **No.** Both consume the same
   `RobotView` objects from the same episode loop, and one authoritative
   `forward_opening_evidence`. That hypothesis is eliminated, not assumed away.
3. **Largest contributing condition?** The proposal defect: **65 of 67 steps**.
4. **Was the LINE commitment timer blocking evidence collection?** **No** —
   `locked = 0` from step 41, and evidence was collected from 44.
5. **Did persistence reset unexpectedly?** **No** — the streak rose
   1, 2, 3 … 14 without a single reset.
6. **Coordinate-frame defect?** **No** — one shared function, one frame.
7. **Does the repaired runtime commit early enough?** **Earlier, not early
   enough.** L→K moved from 117 → 88 (α 0.35) and 102 → 73 (α 0.45), against an
   armable step of ~46.
8. **Does it complete K→L→K on the three-cell set?** Partially: 0.10 / 0.30 /
   0.50.
9. **Still fully decentralized?** **Yes** — 0 guard violations, no exit plane,
   no centroid, no coordinator; every robot computes its own action.
10. **Is the remaining blocker only coalescing and epoch count?** **No.** Epoch
    count is now within target (median 2–3). The remaining blocker is residual
    commit latency: ~27–42 steps between armable and commit that this repair did
    not remove.

## 3. The repair

Two lines of behaviour, no parameter changed:

- `latched_local_trigger_v3` records `requested_mode` — LINE for an ENTRY event,
  KEEP for a RECOVERY event.
- `requested_mode_for(epoch)` recovers that direction for a robot that *adopted*
  a propagated token and has no request of its own, from its own lifecycle state
  alone (committed KEEP + latch before passage ⇒ LINE; committed LINE + latch
  inside ⇒ KEEP). This is local and deterministic; the first attempt at the
  repair failed precisely because adopting robots fell back to the lagging
  signal.

No global exit plane, no hard-coded step or coordinate, no use of the scripted
transition time, no central coordinator.

## 4. Measured effect (3 cells × 2 geometry variants × 5 seeds)

| cell | full (before → after) | crossing | dwell | collision-free | median epochs | L→K step |
|---|---|---|---|---|---|---|
| α 0.25 | 0.00 → **0.10** | 0.20 | 0.10 | 1.00 | 3 | 83 |
| α 0.35 | 0.00 → **0.30** | 1.00 | 0.30 | 1.00 | **2** | 88 |
| α 0.45 | 0.00 → **0.50** | 1.00 | 0.50 | 1.00 | **2** | 73 |

No-op epochs fell to **zero**, which is why two tests that had pinned their
presence correctly went red and were rewritten.

## 5. Gates

| gate | result |
|---|---|
| **T1** trace consistency | **PASS** — one trace, one detector, no global geometry |
| **T2** explained delay | **PASS** — 65/67 steps assigned to a confirmed defect; decomposition sums exactly |
| **T3** nominal latency | **FAIL** — commit still ~27–42 steps after armable |
| **T4** mechanical recovery | **FAIL** — full 0.50 best vs ≥ 0.70; crossing 1.00 in two cells; collision-free 1.00 (no degradation) |
| **T5** decentralization | **PASS** — 0 violations, no exit plane, no central initiation |
| epoch count (reported, not gated) | median **2–3**, down from 8 |

## 6. Remaining blocker

Between armable (~46) and commit (~73–88) there are still ~27–42 unexplained
steps. The single-robot decomposition above was built on the *pre-repair* trace;
regenerating the golden trace against the repaired runtime and repeating the
decomposition is the immediate next step, and it is **not** done here.

Nothing was tuned to improve the numbers: persistence, consensus rounds,
commitment duration, `R_obs`, `epsilon_form`, `L_recover` and the corridor
geometry are all exactly as frozen.
