# RVT Decision-State Sampling Protocol

## Initial Phase 9 Budget

Study A permits at most 6,000 train and 1,500 validation decision events:
120 train and 30 validation events per family/team-size cell for the five
training sizes. Each event generates exactly two candidate rollouts and at most
one local view per robot/candidate at its sampling timestamp.

At most 12 decision events may be retained per episode, separated by at least
1.5 s (10 control steps). Exact duplicate feature hashes are suppressed within
an event; repeated near-identical lifecycle/timestamp records are suppressed.
Sampling is 70% event-balanced and 30% trajectory-uniform.

The initial trajectory-source mixture is fixed at 20% each:

1. scripted diagnostic trajectories;
2. always-COMPACT/always-LINE trajectories, balanced within the source;
3. frozen local geometric-selector trajectories;
4. transition-protocol states;
5. bounded perturbation trajectories.

Future policy-visited states have zero initial allocation and are reserved for
an explicitly approved data-aggregation cycle. No DAgger occurs in Phase 8.

Collection includes decisive, both-success, both-fail, early/late evidence,
communication-degraded, readiness-blocked, near-boundary and nominal non-event
states. Family and team budgets are uniform before the label audit. Rare classes
are not oversampled and no class weight is chosen before that audit.
