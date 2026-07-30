# Stage 1 dry-run v1 — INVALID ENGINEERING ARTIFACTS

**Do not use any file in this directory for training, selection, calibration, or
any scientific conclusion.** These are engineering diagnostics from a dry run that
returned **verdict A**.

## Why invalid

1. **`top1_mode_accuracy` was degenerate.** argmax over `[keep_label, line_label]`
   resolves ties to keep, so a constant always-keep predictor scores **0.854**.
   `direct_keep_line_classifier` scored exactly that by learning the majority class.
2. **Closed-loop validation was structurally dead** — 0.000 for all three methods,
   caused by action-head starvation on 457 states (action RMSE 0.150 against a
   target std of ~0.15). The same episodes give the expert 0.450 (keep) and 1.000
   (line).
3. **The classifier target was arbitrary** on non-decisive states: both-succeed and
   both-fail were assigned `keep`.

## Status of the checkpoints

`checkpoints/binary_mode_pilot_dryrun/` was **deleted**, per the Stage 1 rule that
no dry-run checkpoint may be reused after a verdict-A repair.

## Superseded by

`docs/BINARY_MODE_SEED0_DRY_RUN_V2.md` and `results/binary_mode_pilot/dry_run_seed0_v2/`.
