# Reduced-Scope Baseline Contract

## Deployable Baselines

The minimum primary deployable baseline set is frozen as:

1. always COMPACT;
2. always LINE;
3. local geometric COMPACT/LINE selector;
4. direct learned COMPACT/LINE classifier;
5. recoverability selector without consensus;
6. recoverability selector with consensus;
7. full method without residual action;
8. full method with residual action, only if the action hypothesis later passes.

Every online baseline uses the same frozen topology graph, physical parameters,
controller, safety projection, transition execution, metrics and scenario
episodes. Learned baselines use only the primary candidate set. Differences in
information access and communication must be declared per baseline.

## Diagnostic References

The diagnostic reference set is:

9. centralized COMPACT/LINE selector;
10. counterfactual COMPACT/LINE rollout oracle;
11. best fixed COMPACT/LINE topology per episode;
12. always KEEP as an open-space fixed reference.

Items 9-12 are not deployable online baselines. Centralized and counterfactual
references must be labelled offline upper bounds. Always KEEP remains a fixed
reference only; it must never be described as an online selector baseline or
evidence of online KEEP recovery.

Residual action is optional. Baseline 8 is promoted only after a separately
predeclared action-target and evaluation gate shows an advantage over baseline
7 without changing the frozen mechanical architecture.
