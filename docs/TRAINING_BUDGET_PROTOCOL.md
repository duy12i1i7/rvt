# Training and Model-Selection Budget Protocol

Machine-readable report: [`../results/training_budget_report.json`](../results/training_budget_report.json)
Generator: `rvt_swarm/train.py::training_budget_report`
Tests: `tests/test_equal_model_selection_budget.py`

## Why this exists

The reported success margin of RVT-Swarm over the topology-agnostic GNN baseline
was **0.005** (0.315 vs 0.310), from a **single training seed**. Under the
pre-fix configuration the proposed method also received **2.50× the
checkpoint-selection budget**:

```
pre-fix:   {'rvt_swarm': (300 epochs, 30 validation calls),
            'gnn_only':  (120 epochs, 12 validation calls),
            'instant_cert': (120 epochs, 12 validation calls)}   -> equal: False
schema-2:  {'rvt_swarm': (300, 30), 'gnn_only': (300, 30),
            'instant_cert': (300, 30)}                            -> equal: True
```

Because the best checkpoint is drawn from interval-gated validation
evaluations, more epochs means more draws from a noisy selection signal — which
alone can produce a margin of that size. Any comparison under unequal budgets is
uninterpretable regardless of how many episodes are evaluated.

## Budget report

| Field | rvt_swarm | gnn_only | instant_cert |
|---|---|---|---|
| Epochs | 300 | 300 | 300 |
| Optimizer steps | `300 × steps_per_epoch` | `300 × steps_per_epoch` | `300 × steps_per_epoch` |
| Validation interval (epochs) | 10 | 10 | 10 |
| Max validation calls | 30 | 30 | 30 |
| Checkpoints considered (top-k) | 5 | 5 | 5 |
| Early-stopping patience | 40 | 40 | 40 |
| Early-stopping min delta | 1e-4 | 1e-4 | 1e-4 |
| Early-stopping rule | lexicographic validation key, then top-k recheck | same | same |
| Hyperparameter trials | 0 | 0 | 0 |
| Validation scenarios | narrow_passage, dynamic_obstacles | same | same |
| Validation team sizes | 5, 11, 21 | same | same |
| Validation episodes/setting | 4 | 4 | 4 |
| Recheck episodes/setting | 8 | 8 | 8 |
| Training seeds planned | 0–4 | 0–4 | 0–4 |

`steps_per_epoch` is dataset-dependent and identical across methods: all three
train on one shared dataset with one shared batch size (32). It is reported as
`null` until data generation runs, and `max_optimizer_steps` is computed from it.

## Equalisation choices

- **Levelled up, not down.** The baselines were raised from 120 to 300 epochs
  rather than lowering RVT-Swarm to 120. Lowering would equalise more cheaply but
  handicap the proposed method; raising means no method is disadvantaged. Cost:
  baseline training compute rises ~2.5×, bounded in practice by early stopping
  (patience 40).
- **`hyperparameter_trials` is an explicit field**, fixed at 0 because no tuning
  was performed. If tuning is ever added it must be equal across methods, and
  `test_no_hyperparameter_tuning_was_performed` will fail until this document is
  updated.
- **Selection rule is a string in the report**, so an asymmetric rule cannot be
  introduced without the parity test noticing.

## What equal budgets do *not* fix

Equal budgets remove an asymmetry. They do not make the selection signal sound.
Both of the following remain open and must be addressed before any comparative
claim:

1. **Multiple training seeds.** Budget parity across one seed each is still one
   sample per method. The plan is 5 seeds (10 preferred); see PART 9 of the audit.
2. **Selection-signal noise.** With 4 episodes/setting × 2 scenarios × 3 team
   sizes = 24 validation episodes per call, the ranking signal is itself noisy;
   taking the max over 30 such draws is an optimistic estimator for *every*
   method. Equal budgets make that bias equal, not absent.

## Reporting requirement

The budget table above must appear in the experimental-methodology section of any
manuscript using these results, alongside the number of training seeds and the
per-seed values. A reviewer must be able to confirm budget parity without reading
the code.
