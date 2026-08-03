# RVT Residual-Target Diagnostic Audit

The pre-generation audit uses only train/validation layouts and the fixed tiny
budget. It reports finite/valid counts, non-zero rate, saturation, magnitude,
candidate/role/topology distributions, safety compatibility and utility gain
over the base action.

Pass gates are:

- finite values and physical-semantics validity: 100%;
- safety-projection compatibility: 100%;
- residual bound violations: zero;
- non-zero residual fraction in `[0.10,0.95]`;
- saturation fraction no greater than 0.50;
- at least 0.10 of valid samples select a strictly higher-utility local action;
- both candidates, at least three roles and both transition directions are represented before full generation.

If more than 95% of valid targets equal the base action, or the search cannot
improve at least 10%, H4 and primary residual supervision are blocked. The
expert cannot be tuned after learned results. The Phase 8 tiny audit is an
interface/numerical qualification, not evidence that residual learning improves
closed loop.
