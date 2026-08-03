# Phase 9 Counterfactual Rollout Report

The authoritative manifest plans 42,840 candidate-replica jobs. Every event has
COMPACT and LINE groups; F8 and F9 have three replicas per candidate and all
other families have one.

The candidate-specific job seed includes candidate identity. A separate matched
disturbance seed excludes candidate identity, so COMPACT and LINE replica `r`
are committed to the same disturbance realization while retaining distinct job
identities.

No counterfactual job was started because the source canary failed before a
cloneable simulator state existed. Therefore:

| item | count |
|---|---:|
| planned candidate replicas | 42,840 |
| executed replicas | 0 |
| completed replicas | 0 |
| valid negative task outcomes | 0 |
| generation-invalid replicas | 0 |
| matched pairs materialized | 0 |

Matched-state, communication-state, dynamic-obstacle-state and serialized trace
checks are `NOT_EVALUATED`. Diagnostic headroom categories were not used as
rollout labels.

