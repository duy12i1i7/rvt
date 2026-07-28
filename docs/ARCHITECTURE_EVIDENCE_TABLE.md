# Architecture Evidence Table (Task 6)

Component-by-component, from code tracing plus the Task 1–5 diagnostics.
**No new module was added.** The bias throughout is toward the simplest model the
evidence supports.

Sources: `LEARNING_SANITY_AUDIT.md`, `SAFETY_FILTER_ATTRIBUTION_AUDIT.md`,
`TOPOLOGY_SWITCHING_AUDIT.md`, `RECOVERY_SIGNAL_PILOT.md`.

---

## Main table

| Component | Purpose | Used in training? | Used in inference? | Independent evidence | Failure mode | Verdict | Reason |
|---|---|---|---|---|---|---|---|
| **Topology-conditioned action bank** (`models.py:233-261`) | per-mode action residual on a shared base | **Yes** — weighted bank loss (`train.py:136-145`) | **Yes** — sliced by selected mode (`policy_runtime.py:79-85`) | **None isolated.** No variant with a single shared head was ever run | If the selector is unreliable the bank is sliced by a poor index; residual is trained teacher-forced but executed on selected modes (exposure bias) | **Simplify → keep base head, test removing φ_Δ** | Cannot be defended without an isolated shared-head ablation |
| **Topology classifier** (`topology_logits`, consensus + refine) | graph-level mode logits | **Yes** — KL to soft target, or CE when `use_recoverability=False` | **Only as a fallback** when the score map is unavailable | Micro-overfit: **100 % accuracy** — it learns cleanly | Duplicates the score head's ranking role; two mechanisms rank the same three modes | **Demote to baseline** | It is a *comparison point* for the score head, not a component alongside it |
| **Score head** (`φ_score`) | per-mode utility used for selection | **Yes** — MSE + lower-bound + pairwise rank | **Yes** — drives the selector | Task 5 (below) | Ranking accuracy plateaus at 0.78–0.85 even on 64 memorised samples | **Verdict follows Task 5** | Central claim depends on it |
| **Uncertainty head** (`φ_unc`, softplus) | shrink optimistic scores | **Yes** — L1 to `ReLU(r̂ − y)/std(r̂)` | **Yes** — in `r̃ = r̂ − std(r̂)·σ̂` *and again* in the selector key | **None.** Never validated; no calibration test exists | **Target is the model's own in-sample training residual.** It estimates its own optimism with no held-out signal, and enters the decision twice | **REMOVE** | Indefensible as specified; double-counted; `selector_mode="no_uncertainty_adj"` variant tests the cost |
| **Auxiliary head** (`φ_aux`, 4 scalars) | "retain graph context" | **Yes** — MSE to 4 targets | Predicted but **never read** by the selector | **None** | Targets are `formation_scale, bottleneck, progress, split_active` (`dataset.py:302-307`) — **all four are already input node features** (`dataset.py:215-218`, indices 18–20 and 25) | **REMOVE** | It predicts its own inputs. An auxiliary task with zero information content |
| **Hard-negative mining** (`dataset.py:327-344`) | "augment low-margin bottleneck states" | **Yes** — appends a perturbed duplicate | n/a | **None** | Adds Gaussian noise to **action targets only**; node features, edge features, score targets and topology targets are copied unchanged | **REMOVE** | It does not change state difficulty — it injects label noise on the action head. The name describes something the code does not do |
| **Pairwise ranking loss** (`train.py:35-42`) | preserve mode ordering | **Yes** | n/a (shapes the score head) | Micro-overfit shows it **cannot be driven to zero** | Conflicts with score-MSE + lower-bound in the averaged bundle; gradient norm grows to ≈14.6 | **Keep only if Task 5 supports ranking; then isolate it** | It is the only term that targets the quantity the method claims |
| **Lower-bound loss** (`ReLU(r̃ − y)²`) | conservatism | **Yes** | n/a | **None isolated** | Pulls against ranking: penalising overestimation distorts the ordering the rank loss is trying to preserve | **REMOVE or isolate** | Bundled into a 4-way mean; no evidence it helps |
| **Lexicographic selector** (`safety.py:517-535`) | choose the mode | n/a | **Yes** | Task 3 variants (below) | 11 tie-break levels + an undocumented `score ≥ 0` pre-filter and persistence rule (`safety.py:504-515`); the paper describes 10 | **Simplify to `argmax` + keep tie-break** | Hand rule with more degrees of freedom than the learned signal it arbitrates |
| **Adaptive formation scale** (`environment.py:254-322`) | continuous compression | Affects the environment, so it also changes the data | **Yes** | Smoke ablation was **confounded** — the flag changes the environment, so the variant is evaluated in a different dynamical system | Confounds any ablation that toggles it | **Keep, but re-ablate without the environment confound** | Currently un-evaluable |
| **Safety filter** (`safety.py:132-194`) | risk-triggered projection | No | **Yes** | Task 2 (below) | Blending voids any forward-invariance property the QP would give | **Verdict follows Task 2** | Attribution question |

---

## The six questions the task asks explicitly

**1. Does the auxiliary head predict variables already present in the input?**
**Yes — all four of them.** `aux_target = [formation_scale, bottleneck, progress,
split_active]` (`dataset.py:302-307`). Every one appears verbatim in the node
feature vector (`dataset.py:215-218`): `formation_scale`, `bottleneck`,
`progress` at indices 18–20 and `split_active` at index 25. The head is fed
`pooled_ctx = [pooled_latent ‖ pooled_raw_input]`, where `pooled_raw_input` is the
mean of exactly those node features — and those four are **graph-level constants
broadcast to every node**, so their pooled mean *is* the target. The task is
identity-recoverable from its own input. **Remove.**

**2. Does hard-negative mining change state difficulty or add target noise?**
**Target noise.** The block copies `node_x`, `edge_index`, `edge_attr`,
`recover_scores_target`, `topology_target`, `topology_target_dist` and
`aux_target` unchanged, and perturbs only `action_target_*` with Gaussian noise
scaled by `1 − recover_margin`. The *state* is identical; only the action label
moves. This is label-noise augmentation on the action head, mislabelled as hard
negatives. **Remove or rename and re-justify.**

**3. Is uncertainty calibrated?** **No, and it cannot be as specified.** Its
regression target is `ReLU(r̂ − y)/std(r̂)` computed on the *training* batch —
the model's own in-sample optimism. There is no held-out signal, no calibration
test, and no experiment isolating it. It then enters the decision twice: once
inside `r̃` and once as `−σ̂` at level 6 of the selector key. **Remove.**

**4. Do the classifier and score head duplicate each other?** **Yes.** Both
produce a ranking over the same three modes from the same pooled context;
`choose_counterfactual_topology` uses the score map and keeps the classifier only
as a fallback (`safety.py:546-556`), with the classifier prior explicitly zeroed
so it "cannot override the recoverability-margin ordering". The paper's
`−Recoverability` ablation is precisely a swap between them. Keeping both as
*components* is redundant; keeping the classifier as a *baseline* is exactly right.

**5. Does the selector overwhelm the learned ranking?** — see
`TOPOLOGY_SWITCHING_AUDIT.md`. Structurally the risk is high: only levels 1–2 of
the key are learned; levels 3–11 are hand-designed preferences, and a `score ≥ 0`
pre-filter plus a persistence rule act *before* any of them.

**6. Does the safety filter overwhelm the learned action?** — see
`SAFETY_FILTER_ATTRIBUTION_AUDIT.md`. The smoke benchmark already showed 88–92 %
activation in narrow passage, which is why Task 2 exists.

---

## Smallest model consistent with the evidence so far

Removing everything with no isolated evidence and no defensible target:

```
shared graph encoder (3 attention message-passing layers, K=6)
  ├─ action head            u_i = tanh(φ_base(h_i))          [+ optional φ_Δ residual]
  └─ score head             r̂_τ = φ_score([h̄ ‖ x̄])
loss:  L = MSE(u, u_expert) + λ · PairRank(r̂, y_rollout)
inference: τ* = argmax_τ r̂_τ  (tie-break: keep)
           optional QP projection, reported separately
```

Removed: uncertainty head, auxiliary head, hard-negative mining, lower-bound
loss, 9 of 11 selector tie-break levels. Demoted: topology classifier → baseline.
Pending: action bank (needs a shared-head ablation), adaptive scale (needs an
unconfounded ablation), safety filter (Task 2).
