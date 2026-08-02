# Robot-Local Transition Readiness

The certificate is `(state, margin)` where state is SAFE, UNSAFE, or UNKNOWN.
The continuous margin is the minimum signed margin across all evaluated local
conditions.  SAFE requires every condition to be known and nonnegative.

The obstacle condition computes distance from each fresh local obstacle surface
to the inflated swept envelope.  The peer condition evaluates fresh one-hop
relative states against the union of source/target nominal-neighbour relations
and the robot-robot clearance; non-nominal nearby peers use conservative bounded
motion.  Observation extent must cover the envelope.  Peer and obstacle age
must not exceed configured maxima.  Current committed source, active lifecycle,
candidate, role, local-slice identity, and fixed membership must agree.

A persistent safety-projection failure, infeasible fallback, nonfinite action,
or action/velocity outside the frozen Phase 6 acceleration semantics is UNSAFE.
Missing observation coverage or required stale/unknown peer information is
UNKNOWN.  An out-of-range peer and an unobserved obstacle are not inputs and
cannot affect the deterministic result.

This certificate only authorizes beginning or continuing the locally observed
segment.  It is recomputed during transition execution.  It does not use a
global map, passage label, complete joint state, target-dwell outcome,
centralized collision checker, learned score, or environment object.
