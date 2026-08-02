# RVT Transition Protocol Schema

The authoritative schema string is `rvt-transition-protocol/v1`.

## Identity and ordering

An immutable intent contains schema, lifecycle ID, epoch ID, originator ID,
source, candidate, event type, timestamp, evidence expiry, canonical token hash,
and validity.  The token hash covers lifecycle, source, candidate, event type,
event timestamp, and evidence expiry, but not the originator.  Thus two robots
introducing the same canonical event produce one lifecycle identity.  The epoch
ID is deterministically derived from that hash.

Only a greater lifecycle ID may supersede an older *inactive* lifecycle.  A
different candidate inside an active lifecycle is an explicit conflict and
aborts.  Equal tokens are duplicates.  A lower ID is stale.  Originator ID is
provenance, never ordering authority.

## Message records

- `TransitionIntent`: the immutable candidate-evaluation request.
- `CandidateScoreMessage`: one robot's scalar, semantics, timestamp, and
  validity.
- `ReadinessMessage`: one robot's SAFE, UNSAFE, or UNKNOWN state and margin.
- `ConfirmationMessage`: one robot's acceptance of exactly one lifecycle and
  candidate.
- `LifecycleStatusMessage`: COMMITTED, ABORTED, COMPLETE, or REARMED status and
  cause.

Every record contains schema, lifecycle, epoch, robot provenance, topology
identity, timestamp, and validity needed by its phase.  Runtime ingestion also
checks fixed membership, active lifecycle, freshness, and current source.

## Wire framing

The wire form is deterministic canonical ASCII JSON inside a binary frame:
magic/version, payload length, payload, and SHA-256 digest.  Decoding rejects a
wrong magic, unknown schema/type, length mismatch, trailing bytes, digest
mismatch, malformed JSON, nonfinite numeric value, invalid enum, robot ID,
topology, lifecycle, or epoch.  Communication reports use `len(frame)` only.
