# Binary Mode Pilot — Stage 1 Dry Run V2 (after repairs 1–6)

Results: `results/binary_mode_pilot/dry_run_seed0_v2/`
Specs: [`DECISIVE_MODE_METRIC_SPECIFICATION.md`](DECISIVE_MODE_METRIC_SPECIFICATION.md) ·
[`DUAL_SUPERVISION_DATA_PROTOCOL.md`](DUAL_SUPERVISION_DATA_PROTOCOL.md)
Supersedes `BINARY_MODE_SEED0_DRY_RUN.md` (verdict A).

Seed 0 · train + validation layouts only · **no final-test access** ·
dense action set **2 672 train / 1 764 val** · recovery set 457/302 (unchanged).

---

## 1. Results

| method | Brier | AUROC | **decisive acc** | always-keep ref | nRMSE | **selector-only** | **end-to-end** |
|---|---|---|---|---|---|---|---|
| `topology_agnostic_gnn` | 0.250 | 0.500 | 0.500 | 0.228 | 0.758† | 0.450 | **0.400–0.550** |
| `direct_keep_line_classifier` | 0.325 | 0.655 | **0.965** | 0.228 | 0.191 | **0.800** | **0.000** |
| `rvt_binary_recovery` | **0.095** | **0.937** | **0.965** | 0.228 | 0.190 | 0.500 | **0.000** |

† The GNN has one action head trained on the keep target only; `nRMSE` scores it
against both keep and line targets, so its value is inflated and **not comparable**
with the mode-conditioned models. Flagged rather than silently reported.

## 2. Verification checklist

| # | Check | Result |
|---|---|---|
| 1 | No arbitrary classifier targets on both-succeed / both-fail | **PASS** — CE masked to decisive states; 5 tests |
| 2 | Decisive-state metrics computed correctly | **PASS** — 12 tests incl. ordering invariance |
| 3 | Dense action data identical across methods | **PASS** — one `build_action_dataset` list, same IDs and order |
| 4 | Equal action-training opportunities | **PASS** — 84 dense batches/epoch × 24 epochs for all three; head terms ride the same steps |
| 5 | Action RMSE materially improved | **PASS** — normalised RMSE **1.00 → 0.190** |
| 6 | Selector-only reported separately from end-to-end | **PASS** |
| 7 | Recovery BCE and classifier loss decrease | **PASS** — BCE Brier 0.144→0.095; classifier total 0.225→0.078 |
| 8 | Classifier no longer rewarded for always predicting keep | **PASS** — see §3 |
| 9 | No final-test access | **PASS** — only `build_layouts("train"/"val")` reachable |
| 10 | Writer exclusivity enforced | **PASS** — lock held; token in every checkpoint |
| — | Original Stage 1 checks 1–10 | **PASS** (re-verified) |

## 3. Repair 1 worked — the degenerate metric is dead

Under the v1 metric an always-keep predictor scored **0.854**. Under the decisive
metric it scores **0.228**, and both mode-conditioned models score **0.965**.

The metric now separates a real selector from a degenerate one by 0.74 rather than
rewarding the degenerate one. The always-keep, always-line and majority-class
references are printed beside every decisive accuracy, so the failure mode cannot
recur silently.

## 4. Repair 2 worked — the classifier learned the decision

With CE masked to decisive states, `direct_keep_line_classifier` went from
learning the majority class (v1) to **decisive accuracy 0.965**. Batches with no
decisive example contribute exactly zero, with no NaN.

## 5. Repair 3/6 worked — action learning is real

Normalised RMSE **0.190** against the v1 value of ≈1.00 (0.150 RMSE / 0.15 std) —
a **5× improvement**, achieved purely by decoupling the supervisions and giving
the action head 2 672 states instead of 457.

## 6. The finding that decides the verdict

**The selector works. The learned low-level controller does not.**

| | selector-only (expert executes) | end-to-end (learned executes) | gap |
|---|---|---|---|
| always-keep reference | 0.450 | — | — |
| `direct_keep_line_classifier` | **0.800** | **0.000** | **0.800** |
| `rvt_binary_recovery` | 0.500 | **0.000** | 0.500 |

Both mode-conditioned models choose modes well — decisive accuracy 0.965, and the
classifier's selector-only success of 0.800 is well above the 0.450 always-keep
reference — yet neither completes a single episode when its own action head
executes.

This matches the interpretation fixed in advance in
`DUAL_SUPERVISION_DATA_PROTOCOL.md` §6: *"selector-only succeeds but end-to-end
fails → low-level action control is the limitation."*

### 6.1 The failure is localised to the line action head

A forced-mode probe with learned execution isolates which head is at fault
(`action_rmse_by_stratum.csv`, `forced_mode_probe.txt`):

| executor | forced **keep** | forced **line** |
|---|---|---|
| expert controller | 0.450 | **1.000** |
| `topology_agnostic_gnn` | 0.550 | — (no line head) |
| `direct_keep_line_classifier` | 0.400 | **0.000** |
| `rvt_binary_recovery` | 0.300 | **0.000** |

Open-loop RMSE, same checkpoints:

| method | keep RMSE | line RMSE |
|---|---|---|
| `topology_agnostic_gnn` | **0.037** | 0.594 (no line head — scored for completeness) |
| `direct_keep_line_classifier` | 0.052 | 0.126 |
| `rvt_binary_recovery` | 0.045 | 0.113 |

**The keep head works. The line head does not work at all.** Learned keep
execution reaches 0.300–0.550 against the expert's 0.450 — non-trivial control.
Learned line execution reaches 0.000 against the expert's 1.000.

End-to-end is 0.000 rather than ≈0.4 precisely *because the selector is working*:
on `line_corridor` and `keep_line_keep` it correctly chooses line, and the line
head then fails. A worse selector would have scored higher end-to-end.

This also rules out the harness-defect hypothesis. Mean action magnitude tracks
the expert (ratio 0.948 for the GNN, 1.019 for `rvt_binary_recovery`), so actions
are not mis-scaled or near-zero, and the same runtime path yields 0.550 under
forced keep. Normalised RMSE 0.190 is a 5× improvement and still not enough for
the line manoeuvre, which threads a corridor in single file and tolerates far
less per-step error than keep — the learning-sanity audit hit the same wall at
12 % relative error.

**Harness note.** The first forced-mode probe was invalid: `_episode` obtained
actions from `infer_learned_action`, which picks the head by the model's own
argmax ([`policy_runtime.py:86`](../rvt_swarm/policy_runtime.py:86)), so the
environment was told "keep" while the line head acted. The two agree on the
end-to-end path, so **no reported v2 number was affected** — `fixed_mode_evaluation`
uses expert execution — but the probe was meaningless until fixed.
`learned_action_for_mode()` now binds the head to the mode, with a regression
test. The table above is from the corrected probe.

## 7. An unexpected result that must not be over-read

`rvt_binary_recovery` dominates on prediction — **Brier 0.095 vs 0.325, AUROC
0.937 vs 0.655** — yet its selector-only success (0.500) is *below* the
classifier's (0.800), on identical decisive accuracy (0.965).

That is the opposite of what gate G3 anticipates. Three readings are possible and
this dry run cannot separate them:

1. 20 validation episodes at 2 per cell — a 0.300 gap is ~6 episodes, well inside
   noise at this sample size;
2. decisive accuracy is equal, so the two differ only on *non-decisive* states,
   where by construction the mode does not change the outcome — the gap may be
   measuring nothing;
3. a genuine effect, in which case better calibration does not imply better
   selection.

**No G3 conclusion is drawn from a single seed with 20 episodes.** It is recorded
because it is exactly the comparison the pilot exists to make, and because it
would be easy to quietly drop an inconvenient direction.

## 8. Verdict

> ### **B — Selector is mechanically valid, but learned low-level control remains unusable. Redesign or isolate the controller before the pilot.**

Not A: all six repairs are verified working, all twenty checks pass, and the
apparatus now measures what it claims to.

Not C: end-to-end task recovery is **0.000** for both mode-conditioned methods.
Running three seeds would produce a closed-loop arm that is uniformly zero, and
gate G2 — which compares closed-loop task recovery against always-keep — would
again be unable to discriminate. That is the same structural failure verdict A
identified, at a different layer.

### Required before Stage 2/3

§6.1 already settles the *why*: the line action head, not the harness and not the
selector. That leaves a choice, which is the user's to make:

1. **Run the pilot as a selector-only study** — learned mode selection with
   trusted expert execution. This directly tests the central hypothesis ("does a
   learned recoverability signal choose modes better than always-keep?"), is
   already implemented, needs no protocol change, and is honest: the paper would
   claim a *mode-selection* result and report end-to-end control as an explicit
   limitation. **Recommended.**
2. **Repair the line action head first**, then run end-to-end. This means more
   capacity or more line-conditioned data — a protocol change requiring re-freeze,
   and no guarantee the corridor manoeuvre is learnable by behaviour cloning at
   this scale. The learning-sanity audit is not encouraging on this point.
3. Report both arms, with end-to-end at 0.000 as a negative result. Defensible,
   but three seeds of a uniformly-zero arm buy nothing that this dry run has not
   already established.

Dry-run v2 checkpoints in `checkpoints/binary_mode_pilot_dryrun_v2/` are
engineering artifacts and **will not be reused** for the pilot.

## 9. What this dry run established

- The metric defect is fixed and guarded by tests that reproduce it.
- The classifier target is no longer arbitrary.
- Action learning improved 5× and is no longer starved.
- Selector-only and end-to-end are cleanly separated — and that separation
  immediately produced the diagnosis.
- `rvt_binary_recovery` reaches **validation AUROC 0.937 / Brier 0.095** on
  geometrically disjoint layouts. Encouraging, one seed, not a result.
