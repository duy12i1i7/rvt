# Phase 9 Recoverability Label Audit

Machine-readable audit:
`results/rvt_fd24/datasets/phase9_label_audit.json`

## Counts

| item | count |
|---|---:|
| planned event slots | 15,300 |
| availability not evaluated | 15,300 |
| valid matched pairs | 0 |
| invalid matched pairs | 0 |
| pairs not materialized | 15,300 |
| emitted robot-candidate rows | 0 |

Positive, negative, COMPACT-only, LINE-only, both-success and both-fail counts
are `null`, not zero. No rollout existed from which to compute a label.

The non-vacuity gates are `NOT_EVALUATED`. There was no class weighting,
oversampling or undersampling. The one failed source job is attributed to
generation infrastructure, not to a task, protocol, safety, numerical or
semantic-timeout outcome.

