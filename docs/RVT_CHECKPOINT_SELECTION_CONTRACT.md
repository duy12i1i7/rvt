# RVT Checkpoint Selection Contract

Schema: `rvt-checkpoint-selection/v1`. Scheduled checkpoints occur every 1,000
optimizer steps. Eligibility requires at least 120 closed-loop validation
episodes, at least 10 episodes per primary family, no invalid run, collision-free
point estimate at least 0.95 and degradation no greater than 0.01 from the
paired base-controller reference.

Eligible checkpoints are selected lexicographically:

1. satisfy the collision constraint;
2. maximize episode task success;
3. minimize recoverability Brier score;
4. maximize decisive-state candidate ranking accuracy;
5. maximize required transition completion;
6. choose the earlier optimizer step.

Task-success values within 0.005 are ties and advance to Brier score. Failed
runs are ineligible and reported. Checkpoints are not selected from training
loss.

Base-controller and residual variants have separate eligible pools. H4 is then
tested by a paired validation gate; residual performance cannot rescue an
otherwise ineligible checkpoint. N=24 zero-shot outcomes are excluded from
Study A checkpoint and hyperparameter selection.
