# Candidate Score Protocol Interface

For robot i and one adopted candidate tau, `score_i_tau` is a robot-local
scalar message.  Its declared semantics are one of:

- `probability_like`: finite value in [0, 1];
- `bounded_diagnostic`: finite value in [-1, 1];
- `unavailable`: no usable scalar and validity false.

Phase 7 uses deterministic scripted `bounded_diagnostic` values only.  These
values are not learned recoverability predictions.  The message carries schema,
lifecycle and epoch IDs, robot ID, candidate, scalar, semantics, timestamp, and
validity.  Runtime validation rejects stale, foreign, malformed, nonfinite, or
out-of-range messages.

The interface deliberately transports no ego graph, obstacle set, joint state,
future label, or model tensor.  It leaves a versioned insertion point for a
future scientifically approved local predictor without activating one.
