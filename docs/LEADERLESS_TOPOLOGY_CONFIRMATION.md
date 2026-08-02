# Leaderless Topology Confirmation

Readiness answers whether all robots can safely begin.  Confirmation separately
answers whether every member commits to the same lifecycle and target.

After all-ready, each robot emits one fresh confirmation naming schema,
lifecycle, epoch, robot, source, candidate, acceptance, timestamp, and validity.
Records flood for `k_confirm` causal rounds.  A robot commits only after it has
one valid accepting record from every fixed member and all records agree.  A
dissenter, stale record, candidate/lifecycle conflict, missing path endpoint, or
temporary disconnection blocks and causes a precommit abort on timeout.

Under the declared symmetric bounded-delay contract all nodes complete the same
round and commit at the common next control boundary.  The simulator delivers
messages; it does not issue a commit command.  No partial commitment is accepted
or hidden as component success.
