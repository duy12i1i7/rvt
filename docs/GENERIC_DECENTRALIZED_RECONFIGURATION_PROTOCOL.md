# Generic Decentralized Reconfiguration Protocol

## Frozen Phase 7 contract

Schema `rvt-transition-protocol/v1` is a leaderless, fixed-membership protocol
for all six directed pairs among KEEP (0), COMPACT (5), and LINE (2).  Every
robot executes the same state machine.  The simulator may deliver bytes over a
declared graph but may not select, certify, confirm, or commit a topology.

The sequence is intent flooding, distributed-minimum diagnostic score
agreement, local readiness, conservative all-ready flooding, topology
confirmation, synchronized commitment, Phase 6 local control, target dwell,
completion, and rearm.  The originator only introduces a canonical event token.
It has no score, readiness, confirmation, action, or completion authority.

All four propagation counts are immutable derived values:

`k_intent, k_score, k_ready, k_confirm >= D_max * (delay_rounds + 1)`.

The fixed membership is the mission's persistent robot-ID set.  A component
that has not received one valid origin record from every member cannot claim
whole-team agreement.  Temporary disconnection therefore blocks and eventually
aborts; it never permits component-local commitment.

Candidate qualification uses externally forced requests and deterministic
synthetic scalar scores only.  The Phase 5 model and residual head are absent
from this protocol call graph.

## Predeclared gates

The gates are frozen before qualification:

- **P7-G1:** zero strict guard violations; no global decision, readiness, exit
  plane, centroid, joint action, or non-neighbour protocol delivery.
- **P7-G2:** intent cannot change topology; originator has no final authority;
  duplicate intent creates no duplicate epoch.
- **P7-G3:** geometric false-SAFE rate is exactly zero; each known premature
  fixture is blocked by at least one UNSAFE or UNKNOWN.
- **P7-G4:** connected-contract intent, valid-score, readiness, and confirmation
  agreement are each 1.00, with no partial commitment.
- **P7-G5:** every admitted N/pair open-space cell has collision-free rate at
  least 0.95, target-dwell completion at least 0.90, no systematic role failure,
  and no persistent deadlock.
- **P7-G6:** premature widening commitment is zero; constrained outer roles
  block; widening proceeds when all become SAFE; infeasible fixtures abort or
  time out without collision.
- **P7-G7:** source-equals-target creates zero epochs; no-op epochs are zero;
  one success creates exactly one committed mode epoch; waiting and duplicates
  do not increment it.
- **P7-G8:** mechanics are reported through N=24 and unsupported cells are
  explicit.
- **P7-G9:** all four round counts meet the declared causal diameter bound and
  violations are detected.
- **P7-G10:** every byte is measured from an actual serialized payload.
- **P7-G11:** learned scores, residual actions, scientific training, final-test
  access, and Phase 8 scenario construction remain absent.

No threshold or margin may be changed after observing transition success.
