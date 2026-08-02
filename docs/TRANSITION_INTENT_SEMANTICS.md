# Transition Intent Semantics

An intent means only: "evaluate this candidate transition."  It is not an
authorization, topology vote, readiness result, command, or joint action.

Permitted Phase 7 sources are a local constriction event, a local opening event,
an externally forced diagnostic, or deterministic test evidence.  Other robots
need not reproduce the originator's physical evidence.  They must validate the
schema, canonical token, timestamp and expiry, lifecycle ordering, fixed
membership of the originator, source consistency, candidate support, and pair
admissibility, then evaluate their own score and readiness.

Equivalent canonical events have the same token regardless of originator.
Different candidates in one lifecycle enter conflict handling.  Duplicate
tokens are suppressed.  No intent changes committed topology or bypasses score,
readiness, all-ready, or confirmation.
