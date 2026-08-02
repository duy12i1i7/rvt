# RVT Transition Message Contract

Phase 7 serializes intent, candidate score, readiness, confirmation, and
lifecycle status records under `rvt-transition-protocol/v1`.  Status covers
commit acknowledgement, abort, completion, and rearm.

Each canonical payload is framed with version magic, an explicit byte length,
and SHA-256 integrity digest.  The decoder validates exact framing and payload
type before constructing an immutable record.  Runtime ingestion then validates
fixed robot membership, lifecycle/epoch, topology IDs, source commitment,
freshness, validity, and phase.  Wrong schema, malformed JSON, nonfinite values,
unknown enum/topology, invalid robot ID, truncation, trailing bytes, and any
payload or digest mutation are rejected.

Counters receive bytes, not integer estimates.  Qualification reports transmit
bytes separately for intent, score, readiness, confirmation, and status, plus
per-robot and per-transition totals.  Retransmissions and timeout traffic remain
in the ledger.  Received-byte diagnostics may be reported separately, while
the headline network cost is actual transmitted frame length.
