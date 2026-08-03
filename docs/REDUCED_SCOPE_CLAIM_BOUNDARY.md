# Reduced-Scope Claim Boundary

## Provisional Primary Claim

> A fully decentralized, leaderless method for recoverability-aware online
> reconfiguration between compact and line formations in variable-size robot
> swarms using local sensing, peer-to-peer communication, robot-local
> transition readiness and robot-local control.

The experimental target is exactly `N in {5, 6, 8, 12, 16, 24}`. Within this
boundary, each robot uses local sensing and peer messages, participates in
leaderless agreement, evaluates its own readiness and computes only its own
action.

## Claims Not Authorized

Phase 7S does not authorize claims of:

- three-topology online reconfiguration;
- online KEEP transitions or nominal KEEP recovery;
- arbitrary topology graphs or arbitrary team size;
- formal safety;
- dynamic membership;
- topology-independent transition feasibility.

COMPACT is a distinct registry topology and operational formation, not renamed
KEEP. KEEP is mechanically controllable as a forced topology. Its online
transitions were investigated, but the frozen controller and safety contract
did not support them reliably over the declared variable-size scope. KEEP was
therefore excluded from the primary online graph before scientific data
generation and model training.

The generic protocol's ability to deserialize KEEP records is compatibility,
not experimental support. Likewise, mechanical construction beyond the
declared cells does not establish closed-loop validation beyond those six team
sizes.
