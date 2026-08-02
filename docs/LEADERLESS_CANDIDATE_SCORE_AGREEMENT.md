# Leaderless Candidate Score Agreement

The Phase 7 aggregation rule is frozen as **distributed minimum** over one
fixed-membership candidate:

`score_agreed = min_i(score_i_candidate)`.

Every original signed-by-digest score record is duplicate-suppressed and flooded
for `k_score` causal rounds.  A robot accepts only when it has one fresh valid
record from every declared member, all records name the same lifecycle, epoch,
candidate, and semantics, and the minimum is at least the configured zero
confirmation margin.  Equal scores are deterministic.  One rejection,
unavailable score, stale message, conflict, or missing member blocks agreement.

No originator override exists.  A disconnected component lacks complete
membership evidence and cannot declare agreement.  The simulator delivers
neighbour bytes but never computes or injects the minimum.
