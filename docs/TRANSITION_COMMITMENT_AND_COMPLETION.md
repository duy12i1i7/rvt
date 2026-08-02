# Transition Commitment and Completion

Commitment occurs exactly once after score, all-ready, and confirmation.  Each
robot changes its own committed topology at the same declared control boundary
and increments its mode-epoch count once.  It then invokes the unchanged Phase
6 robot-local controller with its target local topology slice and unchanged
local safety projection.  No joint action is constructed.

The configured physical commitment duration prevents arbitrary reversal.  Each
robot recomputes local safety/readiness while executing.  Persistent projection
failure, infeasibility, collision, or numerical failure enters emergency abort;
it never performs an implicit topology rollback.

Local target stability is exchanged as lifecycle status.  Offline mechanical
completion additionally requires the frozen Metric V3 target tube, configured
target dwell, collision-free execution, and no unresolved numerical failure.
Metric V3 remains an evaluator: its centroid and full positions are not runtime
inputs.  Dwell and commitment are configured in seconds and converted by the
authoritative runtime derivation, never by raw literals.
