# RVT Recoverability Label Audit Gates

Before recoverability training, report sample, decision-event and episode counts
by split, family, team size, candidate, source topology and joint outcome. Also
report positive rate, four joint-category rates, instability, invalid rollout,
average rollout cost, local-view multiplicity and train/validation differences.

The generator passes only when:

1. each candidate has both positive and negative examples in train and validation;
2. train contains at least 50 and validation at least 20 events for each decisive category;
3. each candidate positive rate lies in `[0.10, 0.90]`, or a scientific-scope review explicitly justifies failure;
4. validation contains at least 30 events from every primary family used for checkpoint selection;
5. Study A training labels contain zero N=24 rows;
6. invalid rollout rate is below 0.02 overall and below 0.05 in every family;
7. stochastic label instability is at most 0.10 per family/candidate;
8. absolute train/validation candidate-positive-rate difference is at most 0.15 and joint-category Jensen-Shannon divergence is at most 0.15;
9. event split leakage and duplicate geometry leakage are zero.

A failed gate blocks training; it does not authorize geometry, target or
threshold tuning against model results. Class weights, focal loss and rare-class
oversampling remain forbidden until this audit is frozen and reviewed.
