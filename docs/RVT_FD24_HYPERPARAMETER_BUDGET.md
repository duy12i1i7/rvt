# RVT-FD24 Hyperparameter Budget

Schema: `rvt-fd24-hyperparameter-budget/v1`.

- optimizer: AdamW;
- learning rates: `{1e-4, 3e-4, 1e-3}`;
- weight decay: `{0, 1e-4}`;
- loss-weight choices: the two frozen loss-contract tuples;
- dropout: fixed `0.0` because architecture is frozen;
- batch: 16 decision-event groups plus at most 256 grouped action rows;
- maximum steps: 50,000; warmup: 2,000;
- gradient norm clip: 1.0;
- validation every 1,000 steps;
- early stopping: 8 validations without 0.002 task-success improvement;
- maximum searched configurations: 12;
- model seeds: `{11,29,47}`; seed 0 is mechanical dry run only.

Comparable learned baselines receive the same maximum steps, seeds, validation
frequency, 12-configuration cap and checkpoint opportunities. Validation alone
selects hyperparameters. Architecture expansion and final-test tuning are
forbidden.

After seed 0, at most one separately approved data-aggregation repair cycle is
allowed if distribution shift is confirmed. That cycle may contain at most two
predeclared DAgger rounds, the previously frozen global limit. Phase 8 runs zero
DAgger rounds.
