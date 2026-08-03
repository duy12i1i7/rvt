# Phase 9B Retry, Timeout and Invalid Policy

## Retries

Semantic generation retries are zero. Collision, rollout failure, simulator
timeout, protocol failure, safety-projection failure, residual-expert
infeasibility and invalid candidate outcome cannot create a new seed, event or
episode.

One infrastructure retry is allowed only for process interruption, worker crash,
temporary storage failure or machine interruption. It preserves the job ID,
seed, input hash, configuration hash, output destination and scientific
denominator. Attempts 0 and 1 are both logged; a second infrastructure retry is
rejected.

## Timeouts

Simulator-semantic timeout remains the frozen Phase 8 family horizon. Wall-clock
limits are immutable:

| job | seconds |
|---|---:|
| source trajectory episode | 600 |
| candidate-replica counterfactual | 900 |
| residual-action cell generation | 1,800 |
| shard finalization | 600 |

A wall-clock timeout is an infrastructure failure and does not become a label.
Only a normally reached simulator-semantic timeout may contribute task semantics.

## Invalid Records

A recoverability pair is valid only when both candidate groups execute, all
required replicas exist, matching is valid, ego graphs are valid and provenance
is complete. Failure of any condition invalidates the complete pair: traces and
the audit denominator remain, no training rows are emitted, and no replacement
is generated. A valid task failure remains a legitimate negative label.

An invalid or infeasible residual expert preserves the base sample and failure
metadata in its audit denominator but emits no target row and causes no
replacement sampling.

## Study A N=24 Seal

Study A N=24 uses validation layouts but is evaluation-only, not final-test data.
Access requires a 64-character frozen Study A checkpoint hash, a completed
validation-selection audit hash, explicit zero-shot authorization and an access
log. Training, early stopping, hyperparameter search and checkpoint selection
purposes are rejected. No repository access event was created in Phase 9B.
