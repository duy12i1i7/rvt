# Phase 9G-A1 Study A Generation Report

## Verdict

**D. Official Study-A generation remains incomplete or has unresolved
operational/integrity failures.**

The unresolved failure is operational, not scientific or dataset-semantic. The
qualified Recoverability executor/profile combination reached its frozen
60-second infrastructure timeout at the same ordered production boundary on
the initial execution and on one exact durable resume. The hard gate stopped
Recoverability validation and all Residual V2 work. No dataset was finalized.

## Authorization

- owner authorization artifact:
  `phase9g_a1_owner_authorization_v1.json`;
- canonical authorization hash:
  `cc42e48fd7b557a53bb2e8f385e0dda776c4c0a9c8ec719c040476d5d9c06a99`;
- Recoverability and Residual V2: authorized only for Study A train/validation;
- Study A N24: sealed, not authorized;
- Study B: not authorized;
- final test: sealed, not authorized;
- training: not authorized.

The pre-start audit passed with four scoped command resolutions, 22 frozen
negative cases, zero negative escapes, and zero official data/training/sealed
domain counters before authorization.

## Recoverability

- official run ID:
  `phase9g-a1-study-a-train-validation-recoverability-20260812T042359Z`;
- profile: 12 workers, one numeric thread per worker, atomic chunk size one,
  60-second infrastructure timeout;
- source episodes: 1,500 scheduled, 25 completed;
- decision events: 7,500 scheduled, 127 completed;
- candidate aggregates: 15,000 scheduled, 254 completed;
- replica executions: 21,000 scheduled, 50 completed;
- positive aggregates: 29;
- valid negative aggregates: 9;
- generation-invalid aggregates: 216;
- reconciled candidate-pair events: 127 (19 labelable, 108 invalid);
- scientific rows in sealed STAGING: 318;
- candidate-internal retries: 0;
- run-level resumes: 1;
- infrastructure timeouts: 2;
- unresolved infrastructure failures: 1;
- duplicate scientific identities: 0;
- partial candidate-pair publications: 0;
- total attempt wall time: 373.760 seconds;
- sampled CPU time: 0.79565 CPU-hours;
- STAGING storage: 5,599,596 bytes;
- dataset manifest hash: not created because finalization was prohibited.

The next incomplete ordered boundary is train event index 127: F2, N=12,
`S0_SCRIPTED_DIAGNOSTIC`, episode 1, event slot 2, control step 400. COMPACT is
inferred from the traceback stopping at `compact = next(results)` after the
first 127 ordered event transactions were durable. This boundary attribution
is an operational inference, not a scientific label.

## Residual V2

The Recoverability hard gate did not pass, so no Residual run identity was
created. Robot episodes, eligible/retained/attempted states, LABELED,
NO_ELIGIBLE_ACTION, candidate evaluations, rows, retries, timeouts, failures,
duplicates, CPU-hours and storage are all zero. No Residual dataset manifest
exists.

## Partial Data Quality

These figures describe incomplete STAGING only and are not a finalized dataset
audit. Among 38 labelable candidate aggregates, 29 were positive (76.32%) and
9 were negative (23.68%). At row level there were 239 positive rows (75.16%)
and 79 negative rows (24.84%). Pair retention at the stop boundary was
19/127 (14.96%).

The 318 rows comprise F1: 192, F2: 96, and F8: 30; N=5: 30, N=8: 192, and
N=12: 96. COMPACT and LINE each contribute 159 rows. These partial-prefix
statistics must not be used for class weighting, sampling, model selection or
training.

## Integrity And Isolation

- unresolved scheduled events: 7,373;
- duplicate scientific identities: 0;
- hash failures: 0;
- schema failures: 0;
- denominator errors within the durable prefix: 0;
- candidate-pair partial publications: 0;
- Study A N24 accesses: 0;
- Study B accesses: 0;
- final-test accesses: 0;
- training operations: 0;
- checkpoints: 0;
- optimizer states: 0;
- hyperparameter trials: 0;
- class weighting: `NOT_SELECTED`.

The incomplete STAGING prefix is preserved read-only. It was not promoted,
sharded, indexed, relabeled, sampled or exposed to training.

## Required Next Step

A separate owner-authorized operational requalification must cover the full
Recoverability production atomic-unit latency envelope and the qualified
executor's timeout behavior. This phase does not increase the timeout, change
workers, alter scientific execution, or continue to Residual V2.

Canonical stop evidence:
`phase9g_a1_operational_stop_v1.json`, hash
`20b7a1dfa75a4bc8bd68eaa08d00eeb9058415c88b823266ab560d7e707795a8`.
