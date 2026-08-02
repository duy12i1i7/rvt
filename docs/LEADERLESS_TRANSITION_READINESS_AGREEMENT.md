# Leaderless Transition Readiness Agreement

Each robot publishes only its own certificate.  Original records are flooded
with duplicate suppression for `k_ready` causal rounds.  Agreement uses the
conservative authorization lattice: SAFE is authorizing; UNSAFE and UNKNOWN are
both blocking, with UNKNOWN retained distinctly for diagnosis.

A robot may declare all-ready only after receiving one fresh valid readiness
record from every fixed member and verifying identical schema, lifecycle,
epoch, source, and candidate.  The resulting margin is the distributed minimum.
One UNSAFE, one UNKNOWN, one stale SAFE, a lifecycle conflict, a missing member,
or a graph-contract violation blocks.  Ordering is irrelevant and the
originator has no special operation.

There is no coordinator or central count.  Each node compares flooded sender
IDs with the immutable mission membership in its own protocol instance.  A
disconnected component is incomplete and cannot claim whole-team readiness.
