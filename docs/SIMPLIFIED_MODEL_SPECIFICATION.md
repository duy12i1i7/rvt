# Simplified Model Specification (Task 1)

Implementation: `rvt_swarm/models.py::RVTSimpleRankPolicy`, `rvt_swarm/train.py::compute_simple_rank_loss`
Tests: `tests/test_simplified_model.py` (14 tests)

**The legacy implementation is untouched** and remains available as
`rvt_full_legacy`; a test asserts it still carries all five original heads.

## 1. Model variants

| Name | What it is | Params |
|---|---|---|
| `rvt_full_legacy` | the original five-head model, unchanged | 467,607 |
| `rvt_simple_rank` | **the simplified model** | **402,183** |
| `gnn_topology_agnostic` | shared encoder + action head only | 343,170 |
| `direct_topology_classifier` | action bank + hard best-mode CE; a **baseline** | 467,607 |
| `fixed_keep_policy` | non-learned: expert with mode pinned to KEEP (`baselines.py`) | 0 |

## 2. Architecture

```
node features x_i (68-d)  ──┐
edge features e_ij (11-d) ──┤
                            ▼
        GraphBackbone: Linear(68→128) + 3 × attention message-passing
                            │  h_i (128-d)
              ┌─────────────┴──────────────┐
              ▼                            ▼  (gradient-detached)
   base_action_head(h_i)          pool(h) ‖ pool(x)   (128 + 68 = 196-d)
   topology_delta_head             ▼
   u_i^(τ) = tanh(base +          score_head → r̂ ∈ R³   over {keep, line, split}
        1[τ≠keep]·Δ)
```

**Inputs:** `node_x` (N×68), `edge_index` (2×E), `edge_attr` (E×11), `batch_index`.
**Outputs:** `actions_by_topology` (N×3×2), `recoverability_scores` (G×3).
`topology_logits`, `aux`, and `uncertainty` are all `None` — asserted by test.

## 3. Loss

```
L = L_action + λ_rank · L_pair_rank            (λ_rank = 1.0, λ_score = 0.0)

L_action    = ½[ MSE(U_keep, u_expert_keep) + Σ_τ ω_τ MSE(U^(τ), u_expert^(τ)) ]
L_pair_rank = softplus sign-consistency over mode pairs with unequal targets
```

If absolute recovery prediction is later wanted it is added as an **explicitly
separate** term, never averaged into a bundle:

```
L = L_action + λ_rank · L_pair_rank + λ_score · L_score      (λ_score > 0)
```

`test_score_term_is_off_by_default_and_separable` asserts it is off by default and
that enabling it adds exactly `λ_score · L_score`.

## 4. Inference

```
τ* = argmax_τ r̂_τ          # plain argmax. No lexicographic key, no tie-breaks,
u_i = U_i[τ*]              # no uncertainty adjustment, no persistence rule,
                           # no score ≥ 0 pre-filter.
```

Three tests confirm the removed machinery cannot influence it:
`selector_mode ∈ {lexicographic, logits_argmax, score_argmax}`, `min_dwell_steps`,
and `use_uncertainty_adjustment` all leave the choice unchanged, and the selected
mode always equals `LEARNED_TOPOLOGY_IDS[argmax(score)]`.

## 5. What was removed, and the evidence for removing it

| Removed | Evidence (Method Audit v2) |
|---|---|
| Uncertainty head + adjustment | Uncalibrated (ECE 0.191); target is its own in-sample residual; removing it **improved** every ranking metric (top-1 0.840 vs 0.827, pairwise 0.814 vs 0.797, Kendall 0.631 vs 0.596) |
| Auxiliary head | All four targets (`formation_scale`, `bottleneck`, `progress`, `split_active`) are already input node features, broadcast to every node, so the pooled input *is* the target |
| Topology-classification head | Ranked about as well as the score head (pairwise 0.810 vs 0.814) — duplication. Retained separately as `direct_topology_classifier` |
| Lower-bound loss | No isolated evidence; pulls against the ranking term it was averaged with |
| Multi-level lexicographic selector | Fixed topology was **identical** to it on every validation metric; 9 of its 11 levels are hand-designed preferences |
| Hard-negative action-label perturbation | Perturbs action labels only — state, score and topology targets are copied unchanged, so it is label noise, not hard-state mining. Disabled via `cfg.audit.use_hard_negative_mining = False` |

## 6. Cost

| | legacy | simplified | Δ |
|---|---|---|---|
| Parameters | 467,607 | 402,183 | **−14.0 %** |
| Heads on the shared encoder | 5 | 2 | −3 |
| Loss terms | 7 (averaged in nested bundles) | **2** | −5 |
| Selector decision levels | 11 + pre-filter + persistence rule | **1** (argmax) | −12 |
| Forward passes / step | 1 | 1 | — |
| Encoder complexity | `O(N·K·d)` | `O(N·K·d)` | unchanged |

## 7. Differences from the legacy model, precisely

1. `recoverability_scores` **is** the raw score head output — no dispersion-scaled
   uncertainty subtraction. Asserted by `test_simplified_model_score_is_not_uncertainty_adjusted`.
2. No graph-level classifier, so there is no fallback path and no
   `use_counterfactual_topology` branch.
3. Selection is `argmax`; the environment's persistence and `score ≥ 0` pre-filter
   never run.
4. The objective is a plain weighted sum, not a mean of means, so `λ_rank` has a
   direct and testable interpretation.

## 8. What is deliberately *not* changed

- The mode set stays `{keep, line, split}` and the templates are untouched.
- The action bank (`φ_Δ` residual) is **kept**, because no shared-head ablation
  exists yet — the audit listed it as "cannot yet be removed or kept".
- The recovery target is still the shaped rollout utility. Retraining on the
  binary recovery event is recommended in `RECOVERY_EVENT_SPECIFICATION.md` §5 but
  is **not** done here, because it is not a simplification.
- No new architectural module was added.
