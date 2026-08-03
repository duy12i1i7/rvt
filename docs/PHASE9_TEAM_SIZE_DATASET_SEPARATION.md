# Phase 9 Team-Size Dataset Separation

## Frozen Study Semantics

Study A training and checkpoint-selection validation are restricted to
`N={5,6,8,12,16}`. Its N=24 data must be held in a separate namespace with
`purpose=zero_shot_size_evaluation_only` and must be inaccessible to training,
early stopping, checkpoint selection and hyperparameter search.

Study B uses `N={5,6,8,12,16,24}` in separate dataset, training, checkpoint and
result namespaces. It cannot support a zero-shot N=24 claim.

The required namespace names are unambiguous:

- `results/rvt_fd24/datasets/study_a_zero_shot/`;
- `results/rvt_fd24/datasets/study_a_n24_eval_sealed/`;
- `results/rvt_fd24/datasets/study_b_with_n24/`.

## Generation Status

No namespace was populated. Phase 8 declares the Study A train/validation event
caps for the five smaller sizes, but it does not declare a generation budget for
the Study A N=24 evaluation set or Study B. Deriving either budget by scaling the
five-size Study A cap would be a new Phase 9 choice, which Phase 9C explicitly
forbids.

No N=24 row entered Study A, but this is an isolation-by-non-generation result,
not a completed dataset-isolation audit. No Study B inclusion claim is made.
