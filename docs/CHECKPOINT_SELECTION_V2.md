# Checkpoint Selection v2 (Task 8)

Raw data: [`../results/scenario_headroom/checkpoint_selection_stability.csv`](../results/scenario_headroom/checkpoint_selection_stability.csv)
Script: `scripts/checkpoint_selection_stability.py` · **Validation layouts only.**

## 1. The defect

The Method Audit found the selector choosing an **epoch-5** `gnn_only` checkpoint
over epoch 60, which had **3× better** action RMSE (0.0618 vs 0.0188 m/s²). With 8
validation episodes, success is quantised to 0.125, so the lexicographic key was
resolved by sampling noise.

## 2. Protocol changes

| | audit | v2 |
|---|---|---|
| Validation episodes per evaluation | 8 | **40** |
| Validation source | shared scenario generators | **disjoint validation layouts** |
| Selection criteria compared | 1 (lexicographic task key) | **5** |
| Ranking uncertainty | not estimated | **400-draw bootstrap over episodes** |

Model: `rvt_simple_rank`, trained on **train layouts only**, snapshots every 4 of
24 epochs, one model seed.

## 3. Criteria compared

| ID | Criterion | Computed on |
|---|---|---|
| A | validation action loss | held-out supervised split |
| B | validation pairwise-ranking loss | held-out supervised split |
| C | validation ranking accuracy | held-out supervised split |
| D | validation closed-loop task success | 40 validation-layout episodes |
| E | predeclared composite `0.5·C + 0.5·D` | both |

## 4. Results

| epoch | A action loss ↓ | B rank loss ↓ | C ranking acc ↑ | D task success ↑ | E composite ↑ |
|---|---|---|---|---|---|
| 4 | 0.01762 | 0.2932 | 0.888 | 0.075 | 0.482 |
| 8 | 0.01196 | 0.2474 | 0.924 | 0.025 | 0.474 |
| 12 | 0.00782 | 0.2239 | 0.926 | 0.450 | 0.688 |
| 16 | 0.00590 | 0.2141 | 0.930 | **0.575** | 0.753 |
| 20 | 0.00498 | 0.2083 | 0.930 | 0.550 | 0.740 |
| 24 | **0.00380** | **0.1995** | **0.932** | **0.600** | **0.766** |

### Bootstrap rank stability (400 draws over the 40 validation episodes)

| Criterion | Modal winner | Stability | Distinct winners |
|---|---|---|---|
| **D** closed-loop success | epoch 16 | **0.470** | **3** |
| **C** ranking accuracy | epoch 24 | spread across all snapshots only **0.043** | — |

## 5. Findings

**The pathology is fixed.** At 40 episodes, closed-loop success rises with epoch
(0.075 → 0.600) and tracks the supervised losses. There is no repeat of the
epoch-5-over-epoch-60 inversion: the criteria now agree on direction.

**But closed-loop success is still not a stable selector.** Even at 40 episodes it
picks three different winners across bootstrap resamples and its modal winner
(epoch 16) commands only **47 %** of draws — while epoch 24 has the higher point
estimate (0.600 vs 0.575). A 47 %-stable criterion is a coin flip between adjacent
checkpoints.

**A, B and C are monotone and stable.** All three improve every snapshot and agree
on epoch 24. C's total spread across the whole training run is 0.043, so it
separates checkpoints weakly but *consistently* — the opposite failure mode from
D, and the far safer one for selection.

**C separates weakly.** From 0.888 at epoch 4 to 0.932 at epoch 24, most of the
gain arrives by epoch 8. C alone would barely distinguish epochs 8–24, which is
why the composite E exists.

## 6. Selection rule

The rule is **given by the task specification**, not chosen from these numbers:

> *"If the paper is about recovery ranking, the primary checkpoint criterion should
> be a validation recovery-ranking metric, with task performance as secondary."*

The Method Audit concluded the defensible claim concerns **recovery ranking**, so:

**Primary: C — validation ranking accuracy. Secondary tie-break: D — validation
closed-loop task success. Reported alongside: A.**

For transparency: these results were observed before this document was written.
The rule was not reverse-engineered from them — it follows from the task's
alignment requirement — but the ordering does happen to coincide with the more
stable criterion, and a reader should weigh that accordingly. **No final-test
layout was loaded at any point**, so the rule cannot have been fitted to test
performance.

Formally:

```
select argmax_epoch ( C_val_ranking_accuracy ,
                      D_val_task_success ,
                      −A_val_action_loss )        # lexicographic, 3 levels
```

Three levels, all validation-only, all reported.

## 7. Requirements still unmet

- **One model seed.** Stability across seeds is unmeasured, and is likely worse
  than the within-seed bootstrap suggests.
- **40 episodes is still small.** D's 47 % stability says so directly. If a
  closed-loop criterion is ever made primary, it needs enough episodes for
  stability ≥ 0.8 — likely several hundred.
- **C is computed on a held-out *supervised* split**, not on validation layouts.
  A layout-level ranking metric would be the stricter quantity and is not yet
  implemented.
- The bootstrap resamples episodes only. Model-seed and data-seed variance are not
  in this interval.
