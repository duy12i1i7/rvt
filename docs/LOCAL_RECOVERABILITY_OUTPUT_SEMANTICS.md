# Local Recoverability Output Semantics

For robot i and candidate topology tau, the FD24 head returns:

```text
local_logit_i_tau in R
local_probability_i_tau = sigmoid(local_logit_i_tau)
```

This is robot-local candidate evidence derived from robot i's own V2 ego graph
and observer-local candidate metadata. It is not yet trained in Phase 5 and is
not claimed to be calibrated or scientifically meaningful.

Three concepts must remain separate:

1. Local candidate evidence is the scalar produced independently by one robot.
2. A future distributed candidate score may combine local evidence through an
   authorized communication/agreement mechanism.
3. An eventual topology decision may use a distributed score plus lifecycle
   and commitment rules.

The Phase 5 head performs only item 1. It has no softmax across robots, no
candidate winner, no whole-swarm probability, no topology commitment, no vote,
and no access to rollout outcomes. A single local probability must never be
reported as whole-swarm recoverability.
