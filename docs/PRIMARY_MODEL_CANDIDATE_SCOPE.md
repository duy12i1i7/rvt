# Primary Model Candidate Scope

## Active Candidates

The primary learned candidate set is exactly and explicitly ordered as:

`candidate_set_primary = (COMPACT, LINE) = (5, 2)`

It is defined by `rvt_swarm.fd24.candidate_scope` and is not derived from the
topology registry. Every primary candidate query contains one COMPACT and one
LINE entry. Input order may vary, but validation canonicalizes the result to
`(COMPACT, LINE)`.

The future candidate-conditioned recoverability target generator, selector
loss, score messages and publication commitment path must use this contract.
Primary recoverability labels and primary selector-loss examples must not be
generated for KEEP.

## KEEP Exclusion

KEEP cannot enter a primary candidate batch or distributed score agreement.
Consequently, no KEEP score or logit can affect primary consensus or topology
commitment. KEEP evaluation is limited to fixed-baseline diagnostics,
historical model comparison and optional offline ablation.

This is an admission rule, not a change to the Phase 5 architecture. The model
and checkpoint vocabulary may retain the compatibility vocabulary
`(KEEP, COMPACT, LINE) = (0, 5, 2)`. Checkpoint validation activates only
COMPACT and LINE and records KEEP as an inactive compatibility ID. No model
layer, feature schema, tensor shape or checkpoint field is changed in Phase 7S.

## Future Integration Gate

Data generation and training have not started. Before either starts, their
entry points must prove that candidate batches pass
`validate_primary_candidate_batch`, score agreement passes
`authorize_primary_score_candidate`, and publication requests pass the frozen
online graph. A full-vocabulary checkpoint alone grants no KEEP authority.
