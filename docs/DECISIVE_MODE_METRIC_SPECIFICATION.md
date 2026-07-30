# Decisive-State Mode Metric Specification (Repair 1)

**Predeclared before any new data generation or retraining.**
Implementation: `rvt_swarm/binary_pilot.py::decisive_mode_metrics`
Tests: `tests/test_decisive_mode_metrics.py`

## 1. The defect this replaces

The v1 metric was `argmax(predicted) == argmax(labels)` with labels ordered
`[keep, line]`. `argmax` resolves ties to index 0, so **both-succeed** and
**both-fail** states were both scored as "keep is the correct answer".

Measured consequence: a constant *always-keep* predictor scored **0.854**, and
`direct_keep_line_classifier` scored exactly that by learning the majority class,
while the model that actually predicted probabilities scored 0.457. The metric
ranked the degenerate model nearly twice as good.

## 2. State classification

For each state, from the two binary Recovery Event V2 labels:

| Class | Condition |
|---|---|
| **A `keep_only`** | keep = 1, line = 0 |
| **B `line_only`** | keep = 0, line = 1 |
| **C `both_succeed`** | keep = 1, line = 1 |
| **D `both_fail`** | keep = 0, line = 0 |

```
decisive_state      = keep_only OR line_only
non_decisive_state  = both_succeed OR both_fail
```

**Only decisive states contribute to mode accuracy.** A non-decisive state has no
correct answer — by construction the choice does not change the outcome — so
scoring one is meaningless in either direction.

## 3. Reported quantities

On the decisive subset:

| Metric | Definition |
|---|---|
| `decisive_accuracy` | fraction of decisive states where the predicted mode matches the successful one |
| `decisive_keep_recall` | of `keep_only` states, fraction predicted keep |
| `decisive_line_recall` | of `line_only` states, fraction predicted line |
| `decisive_balanced_accuracy` | mean of the two recalls |
| confusion matrix | `keep→keep`, `keep→line`, `line→keep`, `line→line` |
| `decisive_coverage` | decisive states / all states |

Reported alongside, on all states:

`both_succeed_prevalence`, `both_fail_prevalence`, `keep_only_prevalence`,
`line_only_prevalence`.

**Headline mode accuracy is never computed by assigning an arbitrary winner to a
non-decisive state.**

## 4. Mandatory reference policies

Every report of `decisive_accuracy` must show, on the **exact same decisive
subset**:

- **always keep** → accuracy = `keep_only / decisive`
- **always line** → accuracy = `line_only / decisive`
- **majority decisive class** → `max(keep_only, line_only) / decisive`

Without these a decisive accuracy is uninterpretable: if 70 % of decisive states
are `line_only`, then 0.70 is what always-line already achieves.

## 5. Ordering invariance

Prediction and target are both reduced to a **sign**:

```
pred_sign   = sign(p_line − p_keep)
target_sign = sign(label_line − label_keep)
correct     = 1.0   if pred_sign == target_sign and pred_sign ≠ 0
              0.5   if pred_sign == 0            (exact tie: no preference expressed)
              0.0   otherwise
```

Swapping the candidate order negates both signs, so every score is preserved.
Exact prediction ties receive 0.5 rather than being silently resolved toward
whichever candidate happens to occupy index 0 — that resolution is exactly what
produced the original defect. Tie counts are reported.

## 6. Regression tests

`tests/test_decisive_mode_metrics.py` proves:

1. a `both_succeed` state is **not** scored as a correct keep decision;
2. a `both_fail` state is **not** scored as a correct keep decision;
3. only `keep_only` and `line_only` states contribute to decisive accuracy;
4. the metric is invariant under swapping the candidate ordering;
5. an always-keep predictor scores exactly the `keep_only` share of the decisive
   subset — reproducing the v1 defect as a *guard*, so it cannot silently return.

## 7. What is not changed

The checkpoint-selection hierarchy (Brier → pairwise ranking accuracy →
constrained closed-loop success), the Recovery Event V2 label definition, gates
G1–G4, and the BCE-only loss are all untouched. This repair changes **reporting
and the classifier target mask only**.
