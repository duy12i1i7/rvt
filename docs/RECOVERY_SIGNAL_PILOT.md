# Recovery-Signal Pilot (Task 5)

Is the learned score predictive of a realised future recovery event?

The quantity is called **"the score"** throughout. Whether it earns the word
*recoverability* is what this pilot decides.

Raw data: [`../results/method_audit/recovery_signal_predictions.csv`](../results/method_audit/recovery_signal_predictions.csv) (1 014 rows)
Metrics: [`../results/method_audit/recovery_signal_metrics.csv`](../results/method_audit/recovery_signal_metrics.csv)
Scripts: `scripts/audit_recovery_signal.py`, `scripts/analyze_recovery_signal.py`

---

## 1. Recovery event — defined before the experiment ran

A candidate rollout counts as **recovered** only if **all** hold over horizon H:

1. no robot–robot collision;
2. no robot–obstacle collision;
3. centroid progress ≥ `MIN_PROGRESS`;
4. entry into the topology-conditioned formation tube;
5. remaining in that tube ≥ `L` consecutive steps;
6. no deadlock;
7. no irreversible collapse.

| Parameter | Value |
|---|---|
| H | 14 steps (matches the training-label horizon) |
| L | 3 steps |
| MIN_PROGRESS | 0.02 normalised |
| Rollouts per (state, mode) | 4 |
| Perturbation | initial position σ = 0.02 m; control noise σ = 0.03 m/s² |
| Rollout seed | 20 250 729 (dedicated stream, disjoint from every split seed) |

The simulator is deterministic, so the perturbations above are the **only**
stochasticity, and they are explicitly documented rather than implicit.

**Sample:** 338 validation states × 3 modes = 1 014 (state, mode) pairs, from
validation episodes in open_field and narrow_passage at N ∈ {5, 11}.
Positive rate **0.331**. (The task suggested 500–2 000 states; 338 was reached
within the compute budget and is reported honestly as the smaller figure.)

## 2. Prediction quality

| Predictor | AUROC | AUPRC | Brier | ECE | False-safe | False-unrecoverable |
|---|---|---|---|---|---|---|
| **learned score (uncertainty-adjusted)** | **0.804** | 0.725 | 0.200 | **0.191** | 0.382 | 0.262 |
| **learned score (raw head)** | **0.808** | 0.729 | 0.198 | 0.190 | 0.379 | 0.256 |
| topology classifier logit | 0.758 | 0.714 | 0.208 | 0.186 | 0.383 | 0.265 |
| raw counterfactual rollout utility *(oracle — uses the simulator)* | **0.918** | 0.883 | 0.190 | 0.275 | 0.310 | 0.116 |
| minimum clearance | 0.637 | 0.432 | 0.252 | 0.179 | 0.444 | 0.387 |
| formation error (negated) | 0.638 | 0.453 | 0.258 | 0.198 | 0.423 | 0.345 |
| instantaneous collision risk (negated) | 0.636 | 0.423 | 0.242 | 0.153 | 0.444 | 0.387 |
| distance to goal (negated) | 0.460 | 0.328 | 0.309 | 0.274 | 0.538 | 0.577 |

Scores are not probabilities, so Brier/ECE use a z-score→sigmoid map; they measure
*calibratability of the shape*, not of the raw output.

## 3. Mode-ranking quality

| Predictor | Top-1 mode accuracy | Pairwise accuracy | Kendall τ |
|---|---|---|---|
| learned score (uncertainty-adjusted) | 0.827 | 0.797 | 0.596 |
| **learned score (raw head)** | **0.840** | **0.814** | **0.631** |
| topology classifier logit | 0.827 | 0.810 | 0.623 |
| raw rollout utility *(oracle)* | **0.905** | **0.908** | **0.821** |
| any state-level geometric heuristic | 0.827 | 0.000 | 0.000 |

231 states had a discriminative outcome (not all modes tied).

### The most important number in this table

Minimum clearance, formation error, distance-to-goal and instantaneous risk are
**state-level** quantities — identical across the three modes. Their "top-1
accuracy" of 0.827 is therefore just the **always-choose-`keep`** baseline.

> **Always choosing `keep` achieves top-1 mode accuracy 0.827.
> The learned score achieves 0.840 (raw) / 0.827 (adjusted).**

The learned score's advantage over never thinking about modes at all is **+0.013
top-1, or zero for the shipped uncertainty-adjusted variant**. This is the
quantitative counterpart of the Task 3 finding that the trained selector never
switches: there is almost no headroom for mode selection in these scenarios.

## 4. Calibration

Reliability, 5 equal-mass bins (uncertainty-adjusted score):

| bin | score range | n | mean score | empirical recovery |
|---|---|---|---|---|
| 1 | (−∞, −0.256] | 203 | −0.745 | **0.052** |
| 2 | (−0.256, +0.249] | 203 | +0.016 | 0.228 |
| 3 | (+0.249, +0.522] | 202 | +0.395 | **0.213** ← inversion |
| 4 | (+0.522, +0.901] | 203 | +0.686 | 0.333 |
| 5 | (+0.901, +∞) | 203 | +1.150 | **0.817** |

Monotone at the extremes and **non-monotone in the middle** (bin 3 scores higher
than bin 2 but recovers slightly less often). ECE 0.191 against a 0.331 base rate.

**The score is not calibrated.** It separates the extremes well and is
uninformative in the middle two-fifths of its range.

## 5. Decision rules applied

| Rule | Verdict |
|---|---|
| "If the score is not calibrated but ranks modes well, call it a **recovery-ranking score**" | **This is the closest fit.** ECE 0.191 with a mid-range inversion rules out calibration; pairwise 0.81 and Kendall 0.63 are real ranking signal |
| "If it behaves only like the shaped rollout return, call it **counterfactual rollout utility**" | Partly true by construction — it is trained to regress exactly that. But it is a *lossy* distillation: AUROC 0.808 vs the utility's 0.918, top-1 0.840 vs 0.905 |
| "If it fails to beat simple geometric heuristics, **remove recovery prediction as the central contribution**" | **It beats them on prediction** (AUROC 0.808 vs 0.638 best geometric) but **not on the task it exists for**: +0.013 top-1 over always-`keep` |
| "Retain *recovery* in the title only if quality is clearly supported **on held-out validation layouts**" | **Not satisfied.** The splits share the same four scenario generators (documented in `DATA_SPLIT_AND_CHECKPOINT_PROTOCOL.md` §5); these are held-out *seeds*, not held-out *layouts*. The condition as written is not met |

## 6. Verdict

**Call it a recovery-ranking score.** Not *recoverability*, not a probability, not
a certificate.

It is a genuine signal: AUROC 0.808 against a defined binary recovery event,
clearly better than every geometric heuristic tested, and it recovers a
substantial fraction of the oracle rollout utility's discriminative power
(0.808 of 0.918). That is a real, defensible, falsifiable result.

But it does **not** currently support "recovery prediction" as the *central*
contribution, for three reasons:

1. **Selection headroom is tiny.** Always-`keep` scores 0.827 top-1; the score
   scores 0.840. The downstream decision the score exists to make is nearly
   decided by a constant.
2. **Not calibrated**, with a mid-range inversion — so no probabilistic reading,
   and the "false-safe rate" (0.379) is high enough to matter if it were used as
   a safety signal.
3. **No held-out layouts.** The title condition explicitly requires them.

**The uncertainty adjustment should be removed**: the raw head is better on every
ranking metric (top-1 0.840 vs 0.827, pairwise 0.814 vs 0.797, Kendall 0.631 vs
0.596) and marginally better on AUROC. The adjustment costs accuracy and adds an
uncalibrated, in-sample-fitted parameter to the decision.

**The topology classifier nearly matches the score head on ranking** (pairwise
0.810 vs 0.814, Kendall 0.623 vs 0.631, top-1 0.827 vs 0.840). Keeping both as
components is unjustified duplication; the classifier is the natural baseline.

## 7. What would earn the word

- Held-out **layout families**, not just held-out seeds.
- A scenario family with real mode headroom — where always-`keep` is clearly
  suboptimal — otherwise ranking quality cannot translate into control benefit.
- Calibration via a proper scoring rule: train on the **binary** event with BCE
  and M ≥ 8 rollouts, rather than regressing a shaped utility, then re-measure ECE.
- Multiple training seeds.

## 8. Limitations

- 338 states, one model seed, one training budget, two scenario families.
- 4 rollouts per (state, mode) makes `empirical_recovery_rate` coarse (quantised
  to 0.25); the binary label uses a 0.5 threshold on that.
- The rollout policy is the heuristic expert, so the event measures *the expert's*
  recovery ability under that mode, not the learned policy's.
- Brier/ECE depend on the z-score→sigmoid mapping choice; AUROC, top-1, pairwise
  and Kendall do not, and are the load-bearing numbers.
