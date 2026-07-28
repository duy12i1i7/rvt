# Method Audit v2 — Final Report

Branch `research/method-audit-v2`, from tag `benchmark-protocol-v2-smoke`.
Evaluation Protocol V2 semantics unchanged. No final-test data used anywhere.
No manuscript file touched. No performance-superiority claim made.

Supporting documents: [`LEARNING_SANITY_AUDIT.md`](LEARNING_SANITY_AUDIT.md) ·
[`SAFETY_FILTER_ATTRIBUTION_AUDIT.md`](SAFETY_FILTER_ATTRIBUTION_AUDIT.md) ·
[`TOPOLOGY_SWITCHING_AUDIT.md`](TOPOLOGY_SWITCHING_AUDIT.md) ·
[`RECOVERY_SIGNAL_PILOT.md`](RECOVERY_SIGNAL_PILOT.md) ·
[`BASELINE_FIDELITY_V2.md`](BASELINE_FIDELITY_V2.md) ·
[`ARCHITECTURE_EVIDENCE_TABLE.md`](ARCHITECTURE_EVIDENCE_TABLE.md)

---

## 0. Two smoke-benchmark anomalies are retired

Both headline anomalies from the smoke report were **artifacts of the 6-epoch
smoke checkpoint**, not properties of the method. With a 30-epoch
validation-selected model:

| Smoke anomaly | Smoke value | Audit value |
|---|---|---|
| Safety-filter activation, narrow passage | 0.883–0.918 | **0.023** overall |
| Topology switches per 120-step episode | 12.7–14.0 | **0.00** |

The mechanism is the same in both cases: an undertrained score head emits
near-arbitrary per-mode scores, so the selector churns and the
`all_topologies_negative` escalation path forces the filter on. Training fixes
both — and in doing so replaces them with a more consequential finding: **both
mechanisms become inert.**

This is worth stating plainly because I flagged both as possible design defects
in the smoke report. They were not. The correction runs against my earlier
reading.

---

## 1. Can the models learn the expert?

**Yes, unambiguously.** Micro-overfit on 64 samples drives action RMSE to
**0.0014 m/s² (`gnn_only`)** and **0.0048 m/s² (`rvt_swarm`)** against a target
standard deviation of 0.1515 — 0.9 % and 3.2 % relative — with **100 % topology
accuracy** and no NaN/Inf. None of the nine candidate failure modes (target
normalisation, masking, batching, graph construction, detached tensors, loss
wiring, action scaling, output clipping, optimizer configuration) is present.

One exception: `rvt_swarm`'s **pairwise ranking accuracy plateaus at 0.78–0.85**
on a dataset it has otherwise memorised, while topology accuracy is 1.000. It can
memorise *which* mode is best but not the full pairwise *ordering*.

## 2. Is the learned policy undertrained, incorrectly trained, or fundamentally weak?

**Not undertrained.** Curves plateau by epoch ~45; `gnn_only` reaches action RMSE
0.0188 m/s² (≈12 % of target std) with train and validation loss falling together.

**Partly incorrectly trained.** Two defects:
- the ranking objective cannot be fitted even in the micro-overfit limit, and is
  averaged with a lower-bound term that pulls against it;
- the **checkpoint-selection signal is noise-dominated** — with 8 validation
  episodes, success is quantised to 0.125, and the lexicographic rule selected an
  **epoch-5** `gnn_only` checkpoint over epoch 60, which had **3× better** action
  RMSE (0.0618 vs 0.0188).

**Fundamentally weak in closed loop.** Both models imitate the expert to ≈12 %
open-loop action error yet reach only **0.25–0.50** validation success, while the
*same expert they clone* scores **1.000** in the matched open_field N=4 smoke
cell. Small per-step errors compound into states the expert never visited. This is
behaviour-cloning distribution shift — a method-level limitation, not a bug, and
**no amount of further training closes it**.

## 3. Is the safety filter the effective controller?

**No — it is inert.**

- Activation rate **0.023**; median relative intervention **0.000**; only 0.1 % of
  steps see relative intervention > 1.0.
- **Filter on and filter off give identical results to three decimals**
  (success 0.312, coll-free 0.750, goal 0.406, deadlock 0.062).
- All 82 triggers came from `all_topologies_negative` — the *learned score*
  declaring universal unrecoverability. **Zero** came from geometric risk.

The predeclared threshold grid does show the expected trade-off: at ρ=0.50,
activation rises to 0.925, buying +0.031 coll-free and +0.094 goal at **2.5× the
deadlock rate**. No threshold was selected; the apparent best-success cell
(0.344 at ρ=0.65) is **one episode** on 32 and is explicitly called noise.

So the filter is not a safety-controller-dominating hybrid — but it is also not a
contribution. It is a symptom detector for a poor score head.

## 4. Is topology switching useful or chattering?

**Neither. It never happens.** Zero switches over 3 606 validation steps.

**Fixed topology is identical to the shipped selector on every metric.** So are
argmax-logits, all three dwell settings, and all three hysteresis settings. The
only variant that switches at all (argmax-score, 0.09/episode) is *worse*.

Task 5 explains why: **always choosing `keep` achieves top-1 mode accuracy 0.827**
against realised rollout outcomes. There is almost no headroom for mode selection
in these scenarios.

## 5. Is the recovery score predictive of realised recovery?

**Yes as a ranking signal; no as a calibrated predictor; and not usefully as a
selector.**

- AUROC **0.808** (raw head) against a predeclared binary recovery event —
  clearly above every geometric heuristic (best 0.638) and above the topology
  classifier (0.758).
- Recovers a substantial fraction of the oracle rollout utility's power
  (0.808 of **0.918**).
- **Not calibrated**: ECE 0.191, with a non-monotone inversion between reliability
  bins 2 and 3; false-safe rate 0.379.
- **Top-1 selection accuracy 0.840 vs 0.827 for always-`keep`** — a +0.013 gain on
  the decision it exists to make.
- **Held-out layouts do not exist** — the splits share scenario generators — so
  the title condition stated in the task is not met.

Correct name: **recovery-ranking score**.

## 6. Which components have isolated evidence?

| Component | Isolated evidence? | Direction |
|---|---|---|
| Score head | **Yes** (Task 5) | Positive as a ranker; weak as a selector |
| Topology classifier | **Yes** (Tasks 1, 5) | Learns cleanly; ranks ≈ as well as the score head |
| Uncertainty head | **Yes** (Tasks 3, 5) | **Negative** — removing it improves every ranking metric |
| Auxiliary head | **Yes** (code trace) | **Negative** — targets are its own inputs |
| Hard-negative mining | **Yes** (code trace) | **Negative** — perturbs action labels only, not state difficulty |
| Lexicographic selector | **Yes** (Task 3) | Inert — identical to fixed topology |
| Safety filter | **Yes** (Task 2) | Inert — identical to no filter |
| Adaptive formation scale | **No** — ablation confounded (flag changes the environment) | Unknown |
| Action bank (φ_Δ) | **No** — no shared-head variant exists | Unknown |
| Pairwise ranking loss | Partial (Task 1) | Cannot be fitted; conflicts with the lower-bound term |
| Lower-bound loss | **No** | Unknown, suspected harmful |

## 7. Which components should be removed?

**Remove now, on evidence:** uncertainty head · auxiliary head · hard-negative
mining · lower-bound loss · 9 of 11 selector tie-break levels · the safety filter
as a *claimed contribution* (retain as an optional appendix component).

**Demote:** topology classifier → baseline, not component.

**Cannot yet be removed or kept — needs one isolated experiment each:** the
mode-conditioned action residual φ_Δ, and adaptive formation scale (re-ablated
without the environment confound).

## 8. Smallest defensible final model

```
shared graph encoder (3 attention message-passing layers, K = 6)
  ├─ action head   u_i = tanh(φ_base(h_i))
  └─ score head    r̂_τ = φ_score([h̄ ‖ x̄])          over {keep, line, split}

loss       L = MSE(u, u_expert) + λ · PairRank(r̂, y_rollout)
inference  τ* = argmax_τ r̂_τ   (tie-break: keep)
```

Two heads, two loss terms, one tie-break. Everything else awaits evidence.

Given §4 and §5, the honest framing of this model is **a graph controller with an
auxiliary recovery-ranking head**, not a topology-control method.

## 9. What should the central scientific claim be?

**Not** "recoverability-aware topology control". Both halves fail: topology
control is inert, and *recoverability* is not earned.

The claim the evidence currently supports is narrow and negative-leaning, and
should be stated as such:

> A graph controller trained by behaviour cloning can learn, as an auxiliary
> head, a score that ranks candidate formation modes by their short-horizon
> recovery outcome substantially better than geometric heuristics (AUROC 0.81 vs
> 0.64) — but in the scenarios tested this ranking yields almost no control
> benefit, because a fixed `keep` mode is already near-optimal (top-1 0.827).

That is a legitimate contribution only if paired with scenarios where mode choice
*matters*. Finding or building such scenarios is the precondition for any
positive claim.

The strongest *unclaimed* asset in the repository remains the **evaluation
protocol itself** — episode-wide semantics, split separation, seed-role
separation, budget parity, twelve consistency gates. That is publishable
methodology, and it is currently better evidenced than the method.

## 10. What title is currently justified?

None of the recoverability/topology titles. Justified today:

> **Learning to Rank Formation Modes by Short-Horizon Recovery: A Diagnostic Study**

or, if the benchmark work leads:

> **An Evaluation Protocol for Formation-Navigation Benchmarks, with a Diagnostic
> Study of Mode-Ranking Controllers**

Forbidden on current evidence: *Recoverability*, *Topology Control*, *Safe*,
*Resilient*, *Decentralized*.

---

## Final recommendation

> ### **B — Full RVT architecture unsupported; continue with a simplified model.**

Not **A**: the implementation is not invalid. Micro-overfit proves the models
learn, the protocol is mechanically validated, and the score head carries real
signal (AUROC 0.81).

Not **C**: the recovery-ranking idea is *supported as prediction* but **fails its
own decision rule** — no held-out layouts, no calibration, and +0.013 top-1 over
a constant policy. Proceeding to a three-seed pilot would measure a mechanism
with no demonstrated headroom.

Not **D**: topology-conditioned control is the *least* supported option —
zero switches, and fixed topology is identical on every metric.

**B** is the only honest reading: the five-head architecture is unsupported; four
components should be removed on evidence; the two-head model in §8 is what the
data justifies carrying forward.

### Before any three-seed pilot

1. **Find or build scenarios with mode headroom.** Until always-`keep` stops
   scoring 0.827 top-1, no selector can demonstrate value. This is the blocking
   item.
2. **Fix the selection signal.** 8 validation episodes selected a checkpoint 3×
   worse in action RMSE. Raise episode count or select on a lower-variance
   quantity.
3. **Address distribution shift**, or state prominently that the method is
   bounded by its expert — which scored 1.000 where the learned models scored
   0.25–0.50.
4. **Re-ablate adaptive scale** without the environment confound, and run the
   shared-action-head variant.
5. Retrain the score head on the **binary** recovery event with BCE and M ≥ 8
   rollouts, then re-measure calibration.

### Compliance

| Condition | Status |
|---|---|
| Branch `research/method-audit-v2` from the validated benchmark | ✓ (see §0 of the provenance note below) |
| Protocol V2 semantics unchanged | ✓ — instrumentation verified behaviour-neutral by replaying 30 frozen smoke episodes across 5 methods × 6 metrics |
| No final-test results used for architecture selection | ✓ — every diagnostic used training/validation only |
| Manuscript untouched | ✓ |
| No performance-superiority claim | ✓ |
| Three-seed pilot not run | ✓ |

**Provenance note.** The task named `fafafc5` as the branch point. That commit
does **not** contain the spawn-clamp fix (without which consistency check 8 fails)
or the checkpoint provenance stamping (without which check 11 cannot read a schema
version) — both were uncommitted when the smoke run executed. Branching there
would have run this audit on code with a known out-of-bounds spawn defect and no
consistency gate. The branch was therefore taken from `3e93d95`, the first commit
that actually reproduces the validated smoke state, and that commit carries the
`benchmark-protocol-v2-smoke` tag.

**Stopping here for approval.**
