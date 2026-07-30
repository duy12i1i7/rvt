# Diagnostic only — not scientific results

Every result in this directory is **diagnostic**. None may be reported as a
finding about learned decentralized mode selection. Nothing is deleted.

Reasons:

1. **No decision headroom.** `always_line` succeeds in all four validation
   families (1.000) while the best learned arm reaches 0.861. The keep/line
   headroom was established against the *centralized* controller; the
   robot-local controller is better, so line now works everywhere and getting
   the mode wrong carries no penalty.
2. **K_score was selected on an invalid criterion.** The offline Brier sweep is
   nearly flat (0.159 → 0.123, then unchanged) while closed-loop agreement
   depends strongly on consensus. The offline criterion cannot see the effect
   that matters, and the K=1 it chose disables consensus under any delay ≥ 1
   step (agreement 0.933 → 0.039).
3. **Periodic decision epochs degrade performance**: 0.861 → 0.611.
4. **The "Task 6 epoch protocol" arm did not run the Task 6 protocol.**
   `runtime.py` does not import `epoch.py`; it re-decides on an inline timer
   with no trigger tokens and no mode confirmation. See
   `docs/INTERRUPTED_WORKFLOW_RECOVERY_AUDIT.md` §2. Gate D2's
   mode-confirmation criterion is therefore **NOT MEASURED**, not passed.

What remains valid and is carried forward:

- the locality evidence (0 guard violations, 16 guard tests);
- Gate D5, `results/decentralized/gate_d5_local_controller.txt` — the
  robot-local controller executes both modes (keep 0.700 vs centralized 0.450;
  line 1.000 vs 1.000);
- the consensus result (no-consensus 0.250 → with-consensus 0.861 success,
  0.250 → 1.000 agreement), which is what motivates keeping leaderless
  consensus in the v2 design.
