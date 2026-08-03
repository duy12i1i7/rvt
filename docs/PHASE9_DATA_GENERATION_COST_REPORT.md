# Phase 9 Data Generation Cost Report

## Planned Versus Actual

| work type | planned | unique started | completed |
|---|---:|---:|---:|
| source episode | 3,120 | 1 | 0 |
| decision event | 15,300 | 0 | 0 |
| candidate replica | 42,840 | 0 | 0 |
| residual cell | 340 | 0 | 0 |
| recoverability records | 332,900 capacity | 0 | 0 |
| dense residual records | 536,000 capacity | 0 | 0 |

The source canary had two infrastructure attempts: the original attempt and the
single permitted identical retry. Both stopped before simulator step 0. Total
scientific simulator steps, rollout cost, residual-expert calls, semantic task
failures and infrastructure timeouts are 0.

Generation wall-clock, CPU, peak-memory and per-family/per-N simulation costs
were not produced because no generation worker entered the simulator. The
committed planning/canary/audit JSON occupies approximately 56.1 MB, dominated
by the explicit 56,062,786-byte job manifest. No shard storage exists.

