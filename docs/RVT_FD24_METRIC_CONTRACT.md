# RVT-FD24 Metric Contract

Schema: `rvt-fd24-metrics/v1`.

## Episode-Level Primary Metrics

- task success;
- episode-wide collision-free status;
- required final Metric V3 topology dwell;
- successful required transition sequence;
- deadlock;
- completion time in seconds.

## Recoverability Metrics

Brier score, NLL, AUROC, AUPRC, ECE with 10 equal-mass bins, decisive-state
candidate ranking accuracy and decisive-state coverage. AUROC/AUPRC are invalid
for a slice lacking both classes and are reported as such rather than pooled
silently.

## Control Metrics

Residual RMSE in m/s2, normalized RMSE, saturation, safety-projection
intervention, forced-topology closed-loop success and paired base-versus-
residual task success.

## Decentralization and Scaling

Bytes per robot, messages per transition, agreement latency, per-robot inference
latency, total simulator latency, graph-construction latency, memory, average
degree and maximum degree. Actual serialized protocol bytes are used.

Primary metrics are frozen before model results. Secondary diagnostics cannot be
promoted after observation. Metrics are reported pooled and by family, N,
headroom category, communication condition and model seed.
