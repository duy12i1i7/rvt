# RVT-Swarm Implementation Notes (v3)

This version goes beyond the earlier scaffold by adding:

- concrete topology dynamics in the simulator (`keep`, `compress`, `line`, `split_hint`, `recover`)
- rollout-based per-topology recoverability targets
- graph features for bottleneck geometry, local obstacle density, corridor projection, and TTC proxy
- per-topology recoverability score maps with uncertainty-aware selection
- ranking loss for topology ordering consistency
- liveness metrics: deadlock, irreversible collapse, formation recovery time, recoverability FP/FN

Still a research prototype:
- baseline controllers are normalized internal baselines, not exact external reproductions
- recoverability targets are short-horizon counterfactual proxies, not exact viability certificates
- the code is designed as a paper-oriented starting point for further training/tuning/benchmarking
