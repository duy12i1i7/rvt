# RVT-FD24 Research Questions and Hypotheses

## Primary Research Questions

**RQ1 - Recoverability value.** Can candidate-conditioned robot-local
recoverability prediction improve closed-loop COMPACT/LINE selection over a
local geometric selector, a direct learned topology classifier and the
strongest fixed deployable topology?

**RQ2 - Online reconfiguration value.** Does leaderless online
`COMPACT <-> LINE` reconfiguration improve task success over always COMPACT,
always LINE and the best fixed deployable topology selected before an episode?

**RQ3 - Decentralization value.** How much performance is retained relative to
a centralized diagnostic selector when runtime information is restricted to
local sensing, one-hop peer messages, leaderless score agreement, robot-local
readiness and robot-local actions?

## Primary Hypotheses

**H1.** Recoverability selection improves episode task success by at least 0.08
absolute over both direct classification and local geometric selection, while
meeting the frozen collision gate.

**H2.** Online COMPACT/LINE reconfiguration improves episode task success by at
least 0.10 absolute over each fixed topology in predeclared families with
genuine topology headroom.

**H3.** The decentralized full method retains at least 0.85 of centralized
diagnostic task success, with collision-free degradation no greater than 0.01.

Each primary comparison uses paired episodes, a 95% confidence interval and
Holm-corrected familywise alpha 0.05. Practical thresholds are defined in
`RVT_PRACTICAL_SIGNIFICANCE_GATES.md`; significance alone is insufficient.

## Optional Hypotheses

**H4.** The bounded robot-local residual-action head improves paired
closed-loop task success over the verified base controller without violating
safety or latency gates.

**H5.** A checkpoint trained on `N={5,6,8,12,16}` generalizes usefully to N=24.

**H6.** A separate checkpoint trained with N=24 improves N=24 performance
without an absolute task-success degradation greater than 0.03 on the pooled
smaller sizes.

Failure of H4 removes residual action from the primary contribution. Failure of
H5 prevents a zero-shot scalability claim. Failure of H1 or H2 prevents the
full recoverability-aware paper claim. No hypothesis or threshold may be
rewritten after final-test authorization or access.
