# Peer Support Semantics (Task G3)

## The defect

`PEER_SUPPORT_FRACTION = 0.5` served **three different semantics with one
unexplained number**: suppressing a noisy event origin, accepting a propagated
token, and confirming a transition.

## Selected: OPTION A — local origination with persistence

A robot may originate a RECOVERY event from its own persistent valid local
evidence. **Peer support is not required for origination.** The three semantics
are now separate mechanisms:

| concern | mechanism |
|---|---|
| noisy origin | `evidence_persistence_seconds` (0.45 s = 3 steps) |
| token acceptance | freshness, epoch consistency, compatible lifecycle state |
| transition agreement | min/max mode confirmation over `k_confirm = D_max` rounds |

No mode commitment occurs without distributed propagation, score consensus and
confirmation, so removing the origination threshold removes a redundant gate,
not a safety gate. A single robot proposing against a dissenter still cannot
commit (`commit_or_retain` returns False and records a `DisagreementEvent`).

`peer_support_for_recovery` is retained as a **reported diagnostic** and no
longer gates arming, so degree-0 and degree-1 robots need no special case: an
isolated robot is trusted with its own evidence rather than frozen, and its
proposal still cannot commit alone.

Options B (degree-relative support `ceil(q·max(1, deg))`) and C (fault-model
derived) are documented but **not implemented**; `recovery_armable` raises
`NotImplementedError` if the flag is flipped, rather than silently falling back.
